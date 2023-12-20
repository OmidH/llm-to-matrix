import requests
from bs4 import BeautifulSoup


def get_main_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        soup = BeautifulSoup(response.text, 'html.parser')

        main_content = soup.find('main') or soup.find('article') or soup.find('div')

        if main_content:
            return main_content.get_text(strip=True)
        else:
            return "Main content could not be identified."

    except requests.RequestException as e:
        return f"Error: {e}"
