import requests
import feedparser
import random
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ================= കോൺഫിഗറേഷൻ =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
# =================================================

def get_trending_topic():
    rss_url = "https://news.google.com/rss?hl=ml&gl=IN&ceid=IN:ml"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # 30 സെക്കൻഡ് സമയം നൽകുന്നു
        response = requests.get(rss_url, headers=headers, timeout=30)
        feed = feedparser.parse(response.content)
        
        if feed.entries:
            entry = random.choice(feed.entries[:5])
            return f"Topic: {entry.title}"
        else:
            return "ഇന്ത്യയിലെ ഇന്നത്തെ പ്രധാന രാഷ്ട്രീയ അല്ലെങ്കിൽ കായിക ചർച്ചാവിഷയം"
    except Exception as e:
        print("Trending Fetch Error:", e)
        return "ഇന്നത്തെ പ്രധാന സോഷ്യൽ മീഡിയ ട്രെൻഡിങ് വിവാദം"

def get_available_models():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    available_models = []
    try:
        response = requests.get(url, timeout=30)
        data = response.json()
        if 'models' in data:
            for m in data['models']:
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    available_models.append(m['name'].split('/')[-1])
    except Exception as e:
        print("Model Fetch Error:", e)
    return available_models

def get_post_content(topic):
    available_models = get_available_models()
    if not available_models:
        return None, None, None

    preferences = ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-4-argon', 'gemini-3.8-flash-lite', 'gemini-3.6-flash']
    models_to_try = [m for m in preferences if m in available_models]
    if not models_to_try:
        models_to_try = available_models[:4] 
        
    prompt = f"""
    വിഷയം: '{topic}'
    ഈ വിഷയത്തെ അടിസ്ഥാനമാക്കി താഴെ പറയുന്ന 3 കാര്യങ്ങൾ തയ്യാറാക്കുക. 
    മറുപടി കൃത്യമായി '|' ഉപയോഗിച്ച് വേർതിരിച്ചിരിക്കണം. വേറെ ഒന്നും എഴുതരുത്.
    
    ഫോർമാറ്റ്: [ചിത്രത്തിൽ എഴുതാനുള്ള വായനക്കാരെ ചിന്തിപ്പിക്കുന്ന ഒരു വരി മലയാളം ചോദ്യം] | [ഫേസ്ബുക്കിൽ ഇടാനുള്ള വിമർശനാത്മകമായ മലയാളം ക്യാപ്ഷൻ (ഹാഷ്‌ടാഗ് അടക്കം)] | [High quality, watermark free ഫോട്ടോ ഇന്റർനെറ്റിൽ തിരയാനുള്ള 2-3 ഇംഗ്ലീഷ് വാക്കുകൾ]
    """
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            print(f"\n{model} ഉപയോഗിച്ച് പോസ്റ്റ് തയ്യാറാക്കുന്നു (മാക്സിമം 60 സെക്കൻഡ് കാത്തിരിക്കും)...")
            # Gemini-ക്ക് 60 സെക്കൻഡ് സമയം നൽകുന്നു
            response = requests.post(url, headers=headers, json=data, timeout=60)
            result = response.json()
            if 'candidates' in result:
                text = result['candidates'][0]['content']['parts'][0]['text']
                parts = text.strip().split('|')
                if len(parts) >= 3:
                    return parts[0].strip(), parts[1].strip(), parts[2].strip()
            else:
                print(f"പരാജയപ്പെട്ടു (അടുത്ത മോഡലിലേക്ക് മാറുന്നു): {result.get('error', {}).get('message')}")
        except Exception as e:
            print(f"Timeout/Error ({model}): {e}")
            continue
            
    return None, None, None

def fetch_image(query):
    try:
        from ddgs import DDGS
        results = DDGS().images(query, max_results=1)
        if results:
            img_url = results[0]['image']
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(img_url, headers=headers, timeout=30)
            if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
                return Image.open(BytesIO(response.content))
    except:
        pass

    try:
        search_term = " ".join(query.split()[:2]) 
        url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&generator=search&gsrsearch={search_term}&gsrlimit=1&pithumbsize=1000"
        headers = {'User-Agent': 'AutoFBPostBot/1.0'}
        res = requests.get(url, headers=headers, timeout=30).json()
        pages = res.get('query', {}).get('pages', {})
        if pages:
            for page_id in pages:
                img_url = pages[page_id].get('thumbnail', {}).get('source')
                if img_url:
                    img_data = requests.get(img_url, headers=headers, timeout=30).content
                    return Image.open(BytesIO(img_data))
    except:
        pass
        
    img = Image.new('RGB', (1080, 1080), color=(20, 24, 33))
    return img

def add_text_to_image(image, text):
    image = image.convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype("Manjari-Bold.ttf", int(width/15))
    except:
        font = ImageFont.load_default()
        
    draw.rectangle(((0, height - int(height/4)), (width, height)), fill=(0, 0, 0, 220))
    draw.text((30, height - int(height/4.5)), text, font=font, fill="yellow")
    
    image_path = "fb_post.jpg"
    image.save(image_path)
    return image_path

def post_to_facebook(image_path, caption):
    print("ഫേസ്ബുക്കിലേക്ക് പോസ്റ്റ് ചെയ്യുന്നു (മാക്സിമം 60 സെക്കൻഡ് കാത്തിരിക്കും)...")
    url = "https://graph.facebook.com/v18.0/me/photos"
    payload = {'caption': caption, 'access_token': FB_PAGE_ACCESS_TOKEN}
    files = {'source': open(image_path, 'rb')}
    
    try:
        # ഫേസ്ബുക്കിന് 60 സെക്കൻഡ് സമയം നൽകുന്നു
        response = requests.post(url, data=payload, files=files, timeout=60)
        return response.json()
    except Exception as e:
        return {"error": f"Connection Timeout: {e}"}

def main():
    print("സ്ക്രിപ്റ്റ് തുടങ്ങി...")
    topic = get_trending_topic()
    print(f"കണ്ടെത്തിയ വിഷയം: {topic}")
    
    image_text, caption, search_query = get_post_content(topic)
    
    if image_text and caption and search_query:
        print("ഫോട്ടോ ഡൗൺലോഡ് ചെയ്യുന്നു...")
        img = fetch_image(search_query)
        final_img = add_text_to_image(img, image_text)
        res = post_to_facebook(final_img, caption)
        print("ഫേസ്ബുക്ക് മറുപടി:", res)
    else:
        print("പോസ്റ്റ് തയ്യാറാക്കാൻ കഴിഞ്ഞില്ല.")

if __name__ == "__main__":
    main()
