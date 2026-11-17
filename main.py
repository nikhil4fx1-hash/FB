import requests
import feedparser
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ================= കോൺഫിഗറേഷൻ =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
# =================================================

def get_trending_topics():
    rss_url = "https://news.google.com/rss?hl=ml&gl=IN&ceid=IN:ml"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(rss_url, headers=headers, timeout=30)
        feed = feedparser.parse(response.content)
        
        if feed.entries:
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
            
    prompt = f"""
    താഴെ ഇന്നത്തെ പ്രധാന വാർത്തകളുടെ തലക്കെട്ടുകൾ നൽകിയിരിക്കുന്നു:
    {topics_list}
    
    ഇതിൽ നിന്നും ആളുകൾ ഏറ്റവും കൂടുതൽ ചർച്ച ചെയ്യാൻ സാധ്യതയുള്ള, ഏറ്റവും 'Trending' ആയ ഒരു വാർത്ത മാത്രം തിരഞ്ഞെടുക്കുക (ഉദാഹരണത്തിന്: സ്വർണ്ണവില ഇടിഞ്ഞത്, ധോണിയുടെ വിരമിക്കൽ പോലെയുള്ളവ). 
    
    ഈ വാർത്തയെ അടിസ്ഥാനമാക്കി താഴെ പറയുന്ന 3 കാര്യങ്ങൾ മാത്രം കൃത്യമായി '|' ഉപയോഗിച്ച് വേർതിരിച്ച് നൽകുക. ബ്രാക്കറ്റുകളോ മറ്റ് ചിഹ്നങ്ങളോ ഉപയോഗിക്കരുത്.
    
    മാതൃക (ഈ രീതിയിൽ മാത്രം മറുപടി നൽകുക):
    ഇവിടെ ചിത്രത്തിൽ എഴുതാനുള്ള ഒരു വരി മലയാളം ചോദ്യം വരണം | ഇവിടെ ഫേസ്ബുക്കിൽ ഇടാനുള്ള കിടിലൻ മലയാളം ക്യാപ്ഷനും ഹാഷ്‌ടാഗുകളും വരണം | ഇവിടെ ഫോട്ടോ ഇന്റർനെറ്റിൽ തിരയാനുള്ള 2 ഇംഗ്ലീഷ് വാക്കുകൾ വരണം
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
                text = text.replace("[", "").replace("]", "").replace("Caption:", "").replace("Query:", "").strip()
                parts = text.split('|')
                if len(parts) >= 3:
                    return parts[0].strip(), parts[1].strip(), parts[2].strip()
        except Exception as e:
            continue
            
    return None, None, None

def fetch_image(query):
    print(f"തിരയുന്ന ഫോട്ടോ: {query}")
    try:
        from ddgs import DDGS
        results = DDGS().images(query, max_results=3)
        for res in results:
            img_url = res['image']
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(img_url, headers=headers, timeout=20)
            if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
                return Image.open(BytesIO(response.content))
    except Exception as e:
        print("DuckDuckGo Image Error:", e)

    try:
        search_term = " ".join(query.split()[:2]) 
        url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&generator=search&gsrsearch={search_term}&gsrlimit=3&pithumbsize=1000"
        headers = {'User-Agent': 'AutoFBPostBot/1.0'}
        res = requests.get(url, headers=headers, timeout=20).json()
        pages = res.get('query', {}).get('pages', {})
        if pages:
            for page_id in pages:
                img_url = pages[page_id].get('thumbnail', {}).get('source')
                if img_url:
                    img_data = requests.get(img_url, headers=headers, timeout=20).content
                    return Image.open(BytesIO(img_data))
    except Exception as e:
        print("Wiki Image Error:", e)
        
    img = Image.new('RGB', (1080, 1080), color=(40, 44, 52))
    return img

def add_text_to_image(image, text):
    image = image.convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)
    
    # ഗിറ്റ്ഹബ്ബിൽ നേരിട്ട് അപ്‌ലോഡ് ചെയ്ത ഫോണ്ട് ഫയൽ ഉപയോഗിക്കുന്നു
    font_path = "MalayalamFont.ttf"
            
    try:
        font = ImageFont.truetype(font_path, int(width/16))
    except Exception as e:
        print("മുന്നറിയിപ്പ്: മലയാളം ഫോണ്ട് ഗിറ്റ്ഹബ്ബിൽ കണ്ടെത്താനായില്ല! ദയവായി 'MalayalamFont.ttf' എന്ന പേരിൽ ഫയൽ അപ്‌ലോഡ് ചെയ്തിട്ടുണ്ടെന്ന് ഉറപ്പാക്കുക.")
        print("Error:", e)
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
        
        # വെള്ള അക്ഷരങ്ങൾക്ക് ചുറ്റും കറുത്ത ബോർഡർ (Outline)
        draw.text((x_text, y_text), line, font=font, fill="#FFFFFF", stroke_width=5, stroke_fill="#000000")
        y_text += line_height + line_spacing
        
    image_path = "fb_post.jpg"
    image.save(image_path)
    return image_path

def post_to_facebook(image_path, caption):
    print(f"\nക്യാപ്ഷൻ: {caption}")
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
    topics_list = get_trending_topics() 
    
    image_text, caption, search_query = get_post_content(topics_list)
    
    if image_text and caption and search_query:
        print("\nചിത്രത്തിലെ ടെക്സ്റ്റ്:", image_text)
        img = fetch_image(search_query)
        final_img = add_text_to_image(img, image_text)
        res = post_to_facebook(final_img, caption)
        print("ഫേസ്ബുക്ക് മറുപടി:", res)
    else:
        print("പോസ്റ്റ് തയ്യാറാക്കാൻ കഴിഞ്ഞില്ല.")

if __name__ == "__main__":
    main()
