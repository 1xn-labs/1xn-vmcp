import requests
import re

# Step 1: Get auth URL and state
def simple_oauth(server_id: str):
    try : 
        response1 = requests.post(f"http://localhost:8000/api/mcps/{server_id}/auth")
        data = response1.json()
        auth_url = data["data"]["authorization_url"]
        original_state = data["data"]["state"]

        print(f"Step 1: Got auth URL: {auth_url}")
        print(f"Original state: {original_state}")

    # Step 2: Get HTML from auth URL
        response2 = requests.get(auth_url)
        html = response2.text

        print(f"Step 2: Got HTML from auth URL")

    # Step 3: Extract state from HTML
        state_match = re.search(r'state=([a-f0-9]+)', html)
        html_state = state_match.group(1) if state_match else None

        print(f"Step 3: Extracted state from HTML: {html_state}")

    # Step 4: Call callback with extracted parameters
        callback_url = f"https://example-server.modelcontextprotocol.io/mock-upstream-idp/callback?state={html_state}&code=mock-auth-code&userId=f6ce8fed-5608-4750-b724-7c61dae362df"

        print(f"Step 4: Calling callback URL: {callback_url}")

        response3 = requests.get(callback_url)

        print(f"Final response status: {response3.status_code}")
        print(f"Final response URL: {response3.url}")
        print(f"Full response content: {response3.text}")

        if "Authentication Successful" in response3.text:
            print("✅ SUCCESS: Got Authentication Successful message!")
        return "oauth successful"
    except Exception as e:
        print(f"Error: {e}")
        return False