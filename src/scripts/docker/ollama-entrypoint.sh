#!/bin/bash
set -e

# Start Ollama server in background
ollama serve &

# Wait for server to be ready
for i in $(seq 1 30); do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama server ready"
        break
    fi
    sleep 1
done

# Pull required models
TEXT_MODEL=${OLLAMA_TEXT_MODEL:-llama3.1}
VISION_MODEL=${OLLAMA_VISION_MODEL:-llama3.2-vision}

echo "Pulling text model: $TEXT_MODEL"
ollama pull "$TEXT_MODEL"
echo "Text model ready: $TEXT_MODEL"

echo "Pulling vision model: $VISION_MODEL"
ollama pull "$VISION_MODEL"
echo "Vision model ready: $VISION_MODEL"

echo "All models loaded. Ollama ready."
wait
