# Item 14 — Container Hardening Configuration

## Dockerfile Changes

### Backend Dockerfile (`src/backend/Dockerfile`)
```dockerfile
# Use non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

USER appuser

# Read-only root filesystem
# Run with: --read-only --tmpfs /tmp --tmpfs /var/run
```

### Nginx Dockerfile (`src/nginx/Dockerfile`)
```dockerfile
USER nginx:nginx
```

### Whisper Dockerfile (`src/whisper-service/Dockerfile`)
```dockerfile
RUN addgroup --system --gid 1001 whisper && \
    adduser --system --uid 1001 --ingroup whisper whisperuser

USER whisperuser
```

## Docker Compose Additions (`docker-compose.override.yml`)
```yaml
services:
  backend:
    user: "1001:1001"
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
    security_opt:
      - seccomp:ops/seccomp/backend.json
      - apparmor:ops/apparmor/backend.profile
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE

  postgres:
    security_opt:
      - seccomp:ops/seccomp/postgres.json
      - no-new-privileges:true

  redis-broker:
    user: "999:999"  # redis default user
    read_only: true
    tmpfs:
      - /data  # redis persistence dir
    security_opt:
      - no-new-privileges:true

  redis-cache:
    user: "999:999"
    read_only: true
    tmpfs:
      - /data
    security_opt:
      - no-new-privileges:true

  nginx:
    user: "101:101"  # nginx default user
    read_only: true
    tmpfs:
      - /var/cache/nginx
      - /var/run
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
      - NET_RAW

  celery-worker-text:
    user: "1001:1001"
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true

  celery-worker-image:
    user: "1001:1001"
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true

  celery-worker-default:
    user: "1001:1001"
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true

  celery-beat:
    user: "1001:1001"
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
```

## Seccomp Profiles

### `ops/seccomp/backend.json` — Minimal seccomp for Python backend
```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64"],
  "syscalls": [
    {"names": ["accept", "accept4", "access", "arch_prctl", "bind", "brk",
               "clock_getres", "clock_gettime", "clock_nanosleep", "clone",
               "close", "connect", "dup", "dup2", "epoll_create",
               "epoll_create1", "epoll_ctl", "epoll_wait", "eventfd2",
               "exit", "exit_group", "faccessat", "fadvise64", "fallocate",
               "fchmod", "fchmodat", "fchown", "fchownat", "fcntl",
               "fdatasync", "fgetxattr", "flock", "fsync", "ftruncate",
               "futex", "getcwd", "getdents64", "getegid", "geteuid",
               "getgid", "getpeername", "getpid", "getppid", "getrandom",
               "getsockname", "getsockopt", "gettid", "getuid", "ioctl",
               "listen", "lseek", "lstat", "madvise", "mkdirat", "mlock",
               "mmap", "mprotect", "mremap", "munlock", "munmap", "nanosleep",
               "newfstatat", "open", "openat", "pipe2", "poll", "ppoll",
               "pread64", "preadv", "prlimit64", "pselect6", "pwrite64",
               "pwritev", "read", "readlinkat", "readv", "recvfrom",
               "recvmmsg", "recvmsg", "rename", "renameat", "rt_sigaction",
               "rt_sigprocmask", "rt_sigreturn", "rt_sigtimedwait",
               "sched_getaffinity", "sched_yield", "sendfile", "sendmmsg",
               "sendmsg", "sendto", "set_robust_list", "set_tid_address",
               "setitimer", "setsockopt", "shutdown", "sigaltstack",
               "socket", "splice", "statx", "sysinfo", "tgkill",
               "timerfd_create", "timerfd_settime", "umask", "uname",
               "unlink", "unlinkat", "utimensat", "wait4", "write",
               "writev"],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

## AppArmor Profile — `ops/apparmor/backend.profile`
```
#include <tunables/global>

profile workticket-backend flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  #include <abstractions/python>

  # Network access
  network tcp,
  network udp,
  network inet stream,
  network inet dgram,

  # File access (read-only root, specific write paths)
  /tmp/* rw,
  /var/run/* rw,
  /proc/@{pid}/fd/ r,

  # Deny all other writes
  deny /** w,
  deny /** m,
}
```

## Production Verification Script — `ops/scripts/verify-hardening.sh`
```bash
#!/bin/bash
# Verify container hardening compliance

echo "=== Container Hardening Verification ==="

for service in backend celery-worker-text celery-worker-image celery-worker-default celery-beat redis-broker redis-cache; do
  echo "--- Checking $service ---"
  
  # Check user (should not be root)
  USER=$(docker compose exec -T $service id -u 2>/dev/null || echo "unknown")
  if [ "$USER" = "0" ]; then
    echo "FAIL: $service runs as root"
  else
    echo "OK: $service runs as user $USER"
  fi
  
  # Check read-only filesystem
  docker compose exec -T $service touch /test-write 2>&1 | grep -q "Read-only file system"
  if [ $? -eq 0 ]; then
    echo "OK: $service has read-only root"
  else
    echo "WARN: $service may have writable root (manual check required)"
  fi
done

echo "=== Hardening check complete ==="
```
