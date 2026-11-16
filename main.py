import requests
import feedparser
import random
import os
from duckduckgo_search import DDGS
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ================= കോൺഫിഗറേഷൻ =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
# =================================================

def get_trending_topic():
    # ഗൂഗിൾ ന്യൂസ് (മലയാളം) പ്രധാന വാർത്തകൾ 
    rss_url = "https://news.google.com/rss?hl=ml&gl=IN&ceid=IN:ml"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(rss_url, headers=headers)
        feed = feedparser.parse(response.content)
        
        if feed.entries:
            entry = random.choice(feed.entries[:5])
            return f"Topic: {entry.title}"
        else:
            return "ഇന്ത്യയിലെ ഇന്നത്തെ പ്രധാന രാഷ്ട്രീയ അല്ലെങ്കിൽ കായിക ചർച്ചാവിഷയം"
    except Exception as e:
        print("Trending Fetch Error:", e)
        return "ഇന്നത്തെ പ്രധാന സോഷ്യൽ മീഡിയ ട്രെൻഡിങ് വിവാദം"

def get_post_content(topic):
    prompt = f"""
    വിഷയം: '{topic}'
    ഈ വിഷയത്തെ അടിസ്ഥാനമാക്കി താഴെ പറയുന്ന 3 കാര്യങ്ങൾ തയ്യാറാക്കുക. 
    മറുപടി കൃത്യമായി '|' ഉപയോഗിച്ച് വേർതിരിച്ചിരിക്കണം. വേറെ ഒന്നും എഴുതരുത്.
    
    ഫോർമാറ്റ്: [ചിത്രത്തിൽ എഴുതാനുള്ള വായനക്കാരെ ചിന്തിപ്പിക്കുന്ന ഒരു വരി മലയാളം ചോദ്യം] | [ഫേസ്ബുക്കിൽ ഇടാനുള്ള വിമർശനാത്മകമായ മലയാളം ക്യാപ്ഷൻ (ഹാഷ്‌ടാഗ് അടക്കം)] | [High quality, watermark free ഫോട്ടോ ഇന്റർനെറ്റിൽ തിരയാനുള്ള 2-3 ഇംഗ്ലീഷ് വാക്കുകൾ]
    """
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    # 3 വ്യത്യസ്ത മോഡലുകൾ നൽകുന്നു. ഒരെണ്ണം പരാജയപ്പെട്ടാൽ അടുത്തത് എടുക്കും.
    models = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro']
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            print(f"Trying {model}...")
            response = requests.post(url, headers=headers, json=data)
            result = response.json()
            
            if 'candidates' in result:
                text = result['candidates'][0]['content']['parts'][0]['text']
                parts = text.strip().split('|')
                if len(parts) >= 3:
                    return parts[0].strip(), parts[1].strip(), parts[2].strip()
            else:
                print(f"{model} പരാജയപ്പെട്ടു. കാരണം: {result.get('error', {}).get('message', 'Unknown Error')}")
                
        except Exception as e:
            print(f"Error with {model}: {e}")
            
    return None, None, None

def fetch_image(query):
    # API ഇല്ലാതെ DuckDuckGo വഴി ഫ്രീയായി ഫോട്ടോ എടുക്കുന്നു
    try:
        results = DDGS().images(query, max_results=1)
        if results:
            img_url = results[0]['image']
            headers = {'User-Agent': 'Mozilla/5.0'}
            img_data = requests.get(img_url, headers=headers).content
            return Image.open(BytesIO(img_data))
    except Exception as e:
        print("Image Fetch Error:", e)
    return None

def add_text_to_image(image, text):
    image = image.convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)
    
    # മലയാളം ഫോണ്ട് (Manjari-Bold.ttf ഫയൽ റെപ്പോസിറ്ററിയിൽ ഉണ്ടെന്ന് ഉറപ്പാക്കുക)
    try:
        font = ImageFont.truetype("Manjari-Bold.ttf", int(width/15))
    except:
        font = ImageFont.load_default()
        print("ഫോണ്ട് കണ്ടെത്താനായില്ല!")
        
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
    print("ട്രെൻഡിങ് വിഷയം തിരയുന്നു...")
    topic = get_trending_topic()
    print(f"കണ്ടെത്തിയ വിഷയം: {topic}\n")
    
    print("Gemini വഴി പോസ്റ്റ് തയ്യാറാക്കുന്നു...")
    image_text, caption, search_query = get_post_content(topic)
    
    if image_text and caption and search_query:
        print(f"ചോദ്യം: {image_text}\nക്യാപ്ഷൻ: {caption}\nസെർച്ച് കീവേർഡ്: {search_query}\n")
        
        print("ഫോട്ടോ ഡൗൺലോഡ് ചെയ്യുന്നു...")
        img = fetch_image(search_query)
        
        if img:
            print("ചിത്രത്തിൽ മലയാളം എഴുതുന്നു...")
            final_img = add_text_to_image(img, image_text)
            
            print("ഫേസ്ബുക്കിലേക്ക് പോസ്റ്റ് ചെയ്യുന്നു...")
            res = post_to_facebook(final_img, caption)
            print("വിജയകരം! ഫേസ്ബുക്ക് മറുപടി:", res)
        else:
            print("ചിത്രം കണ്ടെത്താനായില്ല.")
    else:
        print("പോസ്റ്റ് തയ്യാറാക്കാൻ കഴിഞ്ഞില്ല.")

if __name__ == "__main__":
    main()
