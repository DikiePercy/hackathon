#!/bin/bash
# Test Ollama integration with RAG system

set -e

echo "=== Testing Ollama Integration ==="
echo ""

# 1. Test Ollama is accessible
echo "1. Testing Ollama accessibility..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "   ✓ Ollama is running"
else
    echo "   ✗ Ollama is not accessible"
    exit 1
fi

# 2. Test model availability
echo ""
echo "2. Checking llama3:8b model..."
if curl -s http://localhost:11434/api/tags | grep -q "llama3:8b"; then
    echo "   ✓ llama3:8b model is available"
else
    echo "   ✗ llama3:8b model not found"
    echo "   Run: ollama pull llama3:8b"
    exit 1
fi

# 3. Test Python backend configuration
echo ""
echo "3. Checking Python backend configuration..."
docker exec hackathon_python env | grep -E "RAG_LLM_PROVIDER=ollama" > /dev/null
echo "   ✓ RAG_LLM_PROVIDER=ollama"

docker exec hackathon_python env | grep -E "RAG_EMBEDDING_PROVIDER=ollama" > /dev/null
echo "   ✓ RAG_EMBEDDING_PROVIDER=ollama"

docker exec hackathon_python env | grep -E "OLLAMA_BASE_URL" > /dev/null
echo "   ✓ OLLAMA_BASE_URL is set"

# 4. Test simple generation from container
echo ""
echo "4. Testing Ollama generation from Docker container..."
docker exec hackathon_python curl -s http://host.docker.internal:11434/api/generate -d '{
  "model": "llama3:8b",
  "prompt": "Hello, world!",
  "stream": false
}' > /tmp/ollama_test.json

if grep -q "response" /tmp/ollama_test.json; then
    echo "   ✓ Ollama is accessible from Docker container"
else
    echo "   ✗ Ollama is not accessible from Docker container"
    cat /tmp/ollama_test.json
    exit 1
fi

rm -f /tmp/ollama_test.json

echo ""
echo "=== All tests passed! ==="
echo ""
echo "Your RAG system is now configured to use Ollama with llama3:8b"
echo ""
echo "Next steps:"
echo "  1. Upload a document via the web interface"
echo "  2. Ask questions about the document"
echo "  3. Monitor logs: docker logs -f hackathon_python"
