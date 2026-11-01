import requests

url = "http://localhost:11434/api/chat"

payload = {
    "model": "qwen3.5:9b",
    "messages": [
        {
            "role": "user",
            "content": "Say hello in one sentence."
        }
    ],
    "stream": False
}

try:
    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()

    result = response.json()

    print("API Status:", response.status_code)
    print("Model Response:", result["message"]["content"])

except requests.exceptions.ConnectionError:
    print("Error: Could not connect to Ollama. Is it running?")

except requests.exceptions.Timeout:
    print("Error: Request timed out.")

except requests.exceptions.HTTPError as e:
    print("HTTP Error:", e)
    print("Response:", response.text)

except (KeyError, ValueError) as e:
    print("Error parsing API response:", e)