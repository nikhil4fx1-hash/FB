import requests
import feedparser
import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ================= കോൺഫിഗറേഷൻ =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
# =================================================

def get_trending_topics():
    # ഗൂഗിൾ ന്യൂസിൽ നിന്നുള്ള യഥാർത്ഥ റിയൽ-ടൈം വാർത്തകൾ എടുക്കുന്നു
    rss_url = "https://news.google.com/rss?hl=ml&gl=IN&ceid=IN:ml"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(rss_url, headers=headers, timeout=30)
        feed = feedparser.parse(response.content)
        
        if feed.entries:
            # ഏറ്റവും പുതിയ 15 വാർത്തകളുടെ തലക്കെട്ടുകൾ AI-ക്ക് കൊടുക്കാൻ എടുക്കുന്നു
            titles = [entry.title for entry in feed.entries[:15]]
            return "\n".join(titles)
        else:
            return "ഇന്ത്യയിലെ ഇന്നത്തെ പ്രധാന ചർച്ചാവിഷയം"
    except Exception as e:
        print("Trending Fetch Error:", e)
        return "ഇന്നത്തെ പ്രധാന സോഷ്യൽ മീഡിയ ട്രെൻഡിങ് വാർത്ത"

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

def get_post_content(topics_list):
    available_models = get_available_models()
    if not available_models:
        return None, None, None

    preferences = ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-4-argon', 'gemini-3.8-flash-lite']
    models_to_try = [m for m in preferences if m in available_models]
    for m in available_models:
        if m not in models_to_try:
            models_to_try.append(m)
            
    # AI-ക്കുള്ള നിർദ്ദേശം: ലിസ്റ്റിൽ നിന്ന് ഏറ്റവും ചൂടേറിയ വാർത്ത മാത്രം എടുക്കാൻ
    prompt = f"""
    താഴെ ഇന്നത്തെ പ്രധാന വാർത്തകളുടെ തലക്കെട്ടുകൾ നൽകിയിരിക്കുന്നു:
    
    {topics_list}
    
    ഇതിൽ നിന്നും ആളുകൾ ഏറ്റവും കൂടുതൽ ചർച്ച ചെയ്യാൻ സാധ്യതയുള്ള, ഏറ്റവും 'Trending' ആയ ഒരു വാർത്ത മാത്രം തിരഞ്ഞെടുക്കുക (ഉദാഹരണത്തിന്: സ്വർണ്ണവില ഇടിഞ്ഞത്, ധോണിയുടെ വിരമിക്കൽ പോലെയുള്ളവ). ആ തിരഞ്ഞെടുത്ത വാർത്തയെ അടിസ്ഥാനമാക്കി താഴെ പറയുന്ന 3 കാര്യങ്ങൾ തയ്യാറാക്കുക. മറുപടി കൃത്യമായി '|' ഉപയോഗിച്ച് വേർതിരിച്ചിരിക്കണം.
    
    ഫോർമാറ്റ്: [ചിത്രത്തിൽ എഴുതാനുള്ള വായനക്കാരെ ചിന്തിപ്പിക്കുന്നതോ ആകർഷിക്കുന്നതോ ആയ ഒരു വരി മലയാളം (വളരെ നീളം കൂടരുത്)] | [ഫേസ്ബുക്കിൽ ഇടാനുള്ള ആളുകളെക്കൊണ്ട് കമന്റ് ചെയ്യിപ്പിക്കുന്ന തരത്തിലുള്ള കിടിലൻ മലയാളം ക്യാപ്ഷൻ (ഹാഷ്‌ടാഗ് അടക്കം)] | [High Quality HD ഫോട്ടോ ഇന്റർനെറ്റിൽ തിരയാനുള്ള 3-4 ഇംഗ്ലീഷ് വാക്കുകൾ]
    """
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            print(f"\n{model} ഉപയോഗിച്ച് പോസ്റ്റ് തയ്യാറാക്കുന്നു...")
            response = requests.post(url, headers=headers, json=data, timeout=60)
            result = response.json()
            if 'candidates' in result:
                text = result['candidates'][0]['content']['parts'][0]['text']
                parts = text.strip().split('|')
                if len(parts) >= 3:
                    return parts[0].strip(), parts[1].strip(), parts[2].strip()
        except Exception as e:
            continue
            
    return None, None, None

def fetch_image(query):
    # HD ഫോട്ടോ ലഭിക്കാൻ ക്വറിയിൽ HD എന്ന് ചേർക്കുന്നു
    hd_query = query + " high resolution HD"
    try:
        from ddgs import DDGS
        results = DDGS().images(hd_query, max_results=1)
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
    
    # സ്റ്റൈലിഷ് ആയ Noto Sans Bold മലയാളം ഫോണ്ട് ഡൗൺലോഡ് ചെയ്യുന്നു
    font_path = "NotoSansMalayalam-Bold.ttf"
    if not os.path.exists(font_path):
        try:
            print("സ്റ്റൈലിഷ് ഫോണ്ട് ഡൗൺലോഡ് ചെയ്യുന്നു...")
            font_url = "https://github.com/googlefonts/noto-fonts/raw/main/unhinted/ttf/NotoSansMalayalam/NotoSansMalayalam-Bold.ttf"
            urllib.request.urlretrieve(font_url, font_path)
        except:
            pass
            
    try:
        font = ImageFont.truetype(font_path, int(width/16))
    except:
        font = ImageFont.load_default()
        
    margin = 40
    max_width = width - (margin * 2)
    
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        try:
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_w = bbox[2] - bbox[0]
        except:
            text_w = font.getsize(test_line)[0]
            
        if text_w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
    if current_line:
        lines.append(" ".join(current_line))
        
    try:
        line_height = draw.textbbox((0, 0), "ക്യ", font=font)[3] - draw.textbbox((0, 0), "ക്യ", font=font)[1]
    except:
        line_height = int(width/16)
        
    line_spacing = 15
    total_text_height = (len(lines) * line_height) + ((len(lines) - 1) * line_spacing)
    
    # കറുത്ത ബാക്ക്ഗ്രൗണ്ട് ബോക്സ് പൂർണ്ണമായും ഒഴിവാക്കി! 
    # ഫോട്ടോയുടെ താഴെയായി ടെക്സ്റ്റ് വെക്കുന്നു
    y_text = height - total_text_height - 50 
    if y_text < 30: 
        y_text = 30
    
    for line in lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
        except:
            text_w = font.getsize(line)[0]
            
        x_text = (width - text_w) / 2
        
        # കിടിലൻ സ്റ്റൈൽ: വെളുത്ത അക്ഷരങ്ങൾക്ക് ചുറ്റും കട്ടിയുള്ള കറുത്ത ബോർഡർ നൽകുന്നു (Text Stroke)
        draw.text((x_text, y_text), line, font=font, fill="#FFFFFF", stroke_width=4, stroke_fill="#000000")
        y_text += line_height + line_spacing
        
    image_path = "fb_post.jpg"
    image.save(image_path)
    return image_path

def post_to_facebook(image_path, caption):
    print("ഫേസ്ബുക്കിലേക്ക് പോസ്റ്റ് ചെയ്യുന്നു...")
    url = "https://graph.facebook.com/v18.0/me/photos"
    payload = {'caption': caption, 'access_token': FB_PAGE_ACCESS_TOKEN}
    files = {'source': open(image_path, 'rb')}
    
    try:
        response = requests.post(url, data=payload, files=files, timeout=60)
        return response.json()
    except Exception as e:
        return {"error": f"Connection Timeout: {e}"}

def main():
    print("സ്ക്രിപ്റ്റ് തുടങ്ങി...")
    # യഥാർത്ഥ വാർത്തകൾ എടുക്കുന്നു
    topics_list = get_trending_topics() 
    
    image_text, caption, search_query = get_post_content(topics_list)
    
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
