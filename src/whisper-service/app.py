import asyncio
import hmac
import ipaddress
import logging
import os
import socket
import tempfile
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

API_KEY = os.getenv("WHISPER_API_KEY", "")
API_KEY_HEADER = os.getenv("WHISPER_API_KEY_HEADER", "X-Api-Key")

security_scheme = HTTPBearer(auto_error=False)


def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> None:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Whisper service not configured - WHISPER_API_KEY must be set")
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication")
    if hmac.compare_digest(credentials.credentials, API_KEY):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")

_model = None
_MAX_FILE_SIZE = 100 * 1024 * 1024
_MAX_CONCURRENT = int(os.getenv("WHISPER_MAX_CONCURRENT", "3"))
_concurrency_semaphore = asyncio.Semaphore(_MAX_CONCURRENT)


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    duration_seconds: float


class URLRequest(BaseModel):
    url: str


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
        logger.info("Loading faster-whisper model '%s'...", model_size)
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("Whisper model '%s' loaded", model_size)
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Whisper Service")
    _get_model()
    yield
    logger.info("Shutting down Whisper Service")


app = FastAPI(title="Whisper Service", version="1.0.0", lifespan=lifespan)


_ALLOWED_HOSTS: list[str] = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
]
_PRIVATE_IP_BLOCKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _resolve_and_validate(hostname: str | None) -> str:
    if hostname is None:
        raise HTTPException(status_code=400, detail="URL must include a hostname")
    if _ALLOWED_HOSTS:
        if hostname not in _ALLOWED_HOSTS:
            raise HTTPException(status_code=400, detail=f"Host {hostname} not in allowlist")
    try:
        addrinfo = socket.getaddrinfo(hostname, 80, family=socket.AF_INET)
        addr: str = addrinfo[0][4][0]  # type: ignore[assignment]
        ip = ipaddress.ip_address(addr)
        for block in _PRIVATE_IP_BLOCKS:
            if ip in block:
                raise HTTPException(
                    status_code=400,
                    detail=f"Requests to private IP range ({ip}) are blocked for security",
                )
        return addr
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to resolve URL: {e}")


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    if parsed.hostname is None:
        raise HTTPException(status_code=400, detail="URL must include a hostname")
    _resolve_and_validate(parsed.hostname)
    return url


async def _download_audio(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    if parsed.hostname is None:
        raise HTTPException(status_code=400, detail="URL must include a hostname")
    hostname: str = parsed.hostname
    resolved_ip = _resolve_and_validate(hostname)
    safe_url = url.replace(hostname, resolved_ip, 1)
    if parsed.port:
        safe_url = safe_url.replace(f":{parsed.port}", "", 1)
    headers: dict[str, str] = {"Host": hostname}
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.get(safe_url, headers=headers)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a")
        tmp.write(resp.content)
        tmp.close()
        return tmp.name


@app.post("/transcribe/url", response_model=TranscriptionResponse)
async def transcribe_url(request: URLRequest, _auth: None = Depends(verify_auth)):
    local_path = None
    async with _concurrency_semaphore:
        try:
            _validate_url(request.url)
            local_path = await _download_audio(request.url)
            model = _get_model()
            segments, info = model.transcribe(local_path, beam_size=5)
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text)
            text = " ".join(text_parts)
            return TranscriptionResponse(
                text=text,
                language=info.language,
                duration_seconds=round(info.duration, 2),
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            raise HTTPException(status_code=500, detail="Transcription failed")
        finally:
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except OSError:
                    pass


@app.post("/transcribe/file", response_model=TranscriptionResponse)
async def transcribe_file(file: UploadFile = File(...), _auth: None = Depends(verify_auth)):
    if file.size and file.size > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {_MAX_FILE_SIZE // (1024*1024)}MB")
    async with _concurrency_semaphore:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or ".tmp")[1])
        try:
            content = await file.read()
            if len(content) > _MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {_MAX_FILE_SIZE // (1024*1024)}MB")
            tmp.write(content)
            tmp.close()
            model = _get_model()
            segments, info = model.transcribe(tmp.name, beam_size=5)
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text)
            text = " ".join(text_parts)
            return TranscriptionResponse(
                text=text,
                language=info.language,
                duration_seconds=round(info.duration, 2),
            )
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            raise HTTPException(status_code=500, detail="Transcription failed")
        finally:
            tmp.close()
            if os.path.exists(tmp.name):
                try:
                    os.remove(tmp.name)
                except OSError:
                    pass


@app.get("/health")
async def health():
    try:
        _get_model()
        return {
            "status": "ok",
            "model_size": os.getenv("WHISPER_MODEL_SIZE", "base"),
            "device": "cpu",
            "auth_configured": bool(API_KEY),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
