import json
import datetime

def netscape_to_json(netscape_file, json_file):
    """Converts Netscape cookies to JSON."""
    cookies = []
    try:
        with open(netscape_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue  # Skip comments and empty lines

                parts = line.split("\t")
                if len(parts) != 7:
                    continue  # Skip invalid lines

                domain, flag, path, secure, expiration, name, value = parts

                cookie = {
                    "domain": domain,
                    "httpOnly": flag == "TRUE",
                    "path": path,
                    "secure": secure == "TRUE",
                    "expires": int(expiration),
                    "name": name,
                    "value": value,
                    "sameSite": "None", #Playwright requires sameSite, add it.
                }
                cookies.append(cookie)

        with open(json_file, "w") as f:
            json.dump(cookies, f, indent=4)

        print(f"Netscape cookies converted to JSON: {json_file}")

    except FileNotFoundError:
        print(f"Error: Netscape cookie file not found: {netscape_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
netscape_file = "cookie.txt"  # Replace with your Netscape cookie file
json_file = "cookies.json"
netscape_to_json(netscape_file, json_file)