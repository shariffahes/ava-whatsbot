
import os
import requests
import urllib.parse
import json

def encode_query(query: str) -> str:
    return urllib.parse.quote(query)

KEY = "my_pal"
LIMIT = 8

def send_reaction(query, reaction_type="GIF"):
    media_type = "webp" if reaction_type == "STICKER" else "mp4"
    search_filter = "sticker" if reaction_type == "STICKER" else None
    response = requests.get(
        "https://tenor.googleapis.com/v2/search?random=true&media_filter=%s&q=%s&key=%s&client_key=%s&limit=%s&searchFilter=%s" % (media_type, encode_query(query), os.getenv("TENOR_API_KEY"), KEY,  LIMIT, search_filter))
    if response.status_code == 200:
        res = json.loads(response.content)
        contents = []
        media = [content.get('media_formats', {}).get(media_type, {}).get('url', None) for content in res.get('results', [])]
        for index, result in enumerate(res.get('results', [])):
            url = media[index]
            if not url:
                continue
            contents.append({"gif_content": result.get('content_description', ''), "index": index})
      
        return {'contents': contents, "media": media, "type": reaction_type}
    return {}