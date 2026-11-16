import requests
import feedparser
import random
import os
import google.generativeai as genai
from duckduckgo_search import DDGS
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ================= കോൺഫിഗറേഷൻ =================
# GitHub Secrets വഴി കൊടുക്കേണ്ട ഡാറ്റകൾ
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
# =================================================

def get_trending_topic():
    # ട്രെൻഡിങ് വിഷയങ്ങൾ എടുക്കാൻ (ഏഷ്യാനെറ്റ് RSS)
    rss_url = "https://malayalam.asianetnews.com/rss/latest-news"
    feed = feedparser.parse(rss_url)
    entry = random.choice(feed.entries[:5])
    return entry.title

def get_post_content(topic):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # കൃത്യമായ പോസ്റ്റ് കിട്ടാനുള്ള പ്രോംപ്റ്റ്
    prompt = f"""
    വിഷയം: '{topic}'
    ഈ വിഷയത്തെ അടിസ്ഥാനമാക്കി താഴെ പറയുന്ന 3 കാര്യങ്ങൾ തയ്യാറാക്കുക. 
    മറുപടി കൃത്യമായി '|' ഉപയോഗിച്ച് വേർതിരിച്ചിരിക്കണം. വേറെ ഒന്നും എഴുതരുത്.
    
    ഫോർമാറ്റ്: [ചിത്രത്തിൽ എഴുതാനുള്ള വായനക്കാരെ ചിന്തിപ്പിക്കുന്ന ഒരു വരി മലയാളം ചോദ്യം] | [ഫേസ്ബുക്കിൽ ഇടാനുള്ള വിമർശനാത്മകമായ മലയാളം ക്യാപ്ഷൻ (ഹാഷ്‌ടാഗ് അടക്കം)] | [High quality, watermark free ഫോട്ടോ ഇന്റർനെറ്റിൽ തിരയാനുള്ള 2-3 ഇംഗ്ലീഷ് വാക്കുകൾ (ഉദാ: Kerala Chief minister high resolution)]
    """
    try:
        response = model.generate_content(prompt)
        parts = response.text.strip().split('|')
        if len(parts) >= 3:
            return parts[0].strip(), parts[1].strip(), parts[2].strip()
    except Exception as e:
        print("Gemini Error:", e)
    return None, None, None

def fetch_image(query):
    # API ഇല്ലാതെ DuckDuckGo വഴി ഫ്രീയായി ഫോട്ടോ എടുക്കുന്നു
    try:
        results = DDGS().images(query, max_results=1)
        if results:
            img_url = results[0]['image']
            img_data = requests.get(img_url).content
            return Image.open(BytesIO(img_data))
    except Exception as e:
        print("Image Fetch Error:", e)
    return None

def add_text_to_image(image, text):
    image = image.convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)
    
    # മലയാളം ഫോണ്ട് (നിങ്ങളുടെ ഗിറ്റ്ഹബ്ബിൽ Manjari-Bold.ttf ഉണ്ടായിരിക്കണം)
    try:
        font = ImageFont.truetype("Manjari-Bold.ttf", int(width/15))
    except:
        font = ImageFont.load_default()
        
    # ഷാഡോ ബോക്സും മഞ്ഞ നിറത്തിൽ അക്ഷരങ്ങളും
    draw.rectangle(((0, height - int(height/5)), (width, height)), fill=(0, 0, 0, 200))
    draw.text((20, height - int(height/6)), text, font=font, fill="yellow")
    
    image_path = "fb_post.jpg"
    image.save(image_path)
    return image_path

def post_to_facebook(image_path, caption):
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
    payload = {'caption': caption, 'access_token': FB_PAGE_ACCESS_TOKEN}
    files = {'source': open(image_path, 'rb')}
    response = requests.post(url, data=payload, files=files)
    return response.json()

def main():
    topic = get_trending_topic()
    print(f"Topic: {topic}")
    
    image_text, caption, search_query = get_post_content(topic)
    print(f"Query: {search_query}")
    
    if search_query:
        img = fetch_image(search_query)
        if img:
            final_img = add_text_to_image(img, image_text)
            res = post_to_facebook(final_img, caption)
            print("Success:", res)
        else:
            print("Image not found")

if __name__ == "__main__":
    main()
