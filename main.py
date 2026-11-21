import requests
import feedparser
import os
import re
import urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
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

    preferences = ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-4-argon']
    models_to_try = [m for m in preferences if m in available_models]
    for m in available_models:
        if m not in models_to_try:
            models_to_try.append(m)
            
    prompt = f"""
    താഴെ ഇന്നത്തെ പ്രധാന വാർത്തകളുടെ തലക്കെട്ടുകൾ നൽകിയിരിക്കുന്നു:
    {topics_list}
    
    ഇതിൽ നിന്നും ആളുകൾ ഏറ്റവും കൂടുതൽ ചർച്ച ചെയ്യാൻ സാധ്യതയുള്ള ഒരു വാർത്ത മാത്രം തിരഞ്ഞെടുക്കുക. ഈ വാർത്തയെ അടിസ്ഥാനമാക്കി താഴെ പറയുന്ന 3 കാര്യങ്ങൾ മാത്രം കൃത്യമായി '|' ഉപയോഗിച്ച് വേർതിരിച്ച് നൽകുക. ബ്രാക്കറ്റുകളോ മറ്റ് ചിഹ്നങ്ങളോ ഉപയോഗിക്കരുത്.
    
    പ്രധാന നിർദ്ദേശം: ക്യാപ്ഷന്റെ ഏറ്റവും താഴെയായി, ഈ പേജ് ഫോളോ ചെയ്ത് സപ്പോർട്ട് ചെയ്യാൻ ആവശ്യപ്പെടുന്ന ആകർഷകമായ ഒരു വരി കൂടി ഉൾപ്പെടുത്തണം.
    
    മാതൃക (ഈ രീതിയിൽ മാത്രം മറുപടി നൽകുക):
    ചിത്രത്തിൽ എഴുതാനുള്ള ആകർഷകമായ ഒരു വരി മലയാളം ചോദ്യം (വളരെ നീളം കൂടരുത്) | ഫേസ്ബുക്കിൽ ഇടാനുള്ള കിടിലൻ മലയാളം ക്യാപ്ഷനും ഫോളോ ചെയ്യാനുള്ള അഭ്യർത്ഥനയും ഹാഷ്‌ടാഗുകളും | ഫോട്ടോ ഇന്റർനെറ്റിൽ തിരയാൻ സഹായിക്കുന്ന 1 അല്ലെങ്കിൽ 2 ലളിതമായ ഇംഗ്ലീഷ് വാക്കുകൾ
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
    search_query = query + " news high quality"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # 1. Bing Images 
    try:
        print("Bing-ൽ തിരയുന്നു...")
        bing_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(search_query)}"
        html = requests.get(bing_url, headers=headers, timeout=20).text
        image_urls = re.findall(r'murl&quot;:&quot;(http[^&]+)&quot;', html)
        for img_url in image_urls:
            try:
                img_resp = requests.get(img_url, headers=headers, timeout=10)
                if img_resp.status_code == 200:
                    img = Image.open(BytesIO(img_resp.content))
                    return img.convert('RGB')
            except:
                continue
    except:
        pass

    # 2. Google Images Scraper
    try:
        print("Google Images-ൽ തിരയുന്നു...")
        google_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}&tbm=isch"
        html = requests.get(google_url, headers=headers, timeout=20).text
        image_urls = re.findall(r'https?://[^"\'\s>]+(?:\.jpg|\.jpeg|\.png)', html)
        for img_url in image_urls:
            if 'gstatic' not in img_url and 'logo' not in img_url.lower():
                try:
                    img_resp = requests.get(img_url, headers=headers, timeout=10)
                    if img_resp.status_code == 200:
                        img = Image.open(BytesIO(img_resp.content))
                        return img.convert('RGB')
                except:
                    continue
    except:
        pass

    print("ഫോട്ടോ കണ്ടെത്താനായില്ല, ഡാർക്ക് ബാക്ക്ഗ്രൗണ്ട് ഉപയോഗിക്കുന്നു.")
    return Image.new('RGB', (1080, 1080), color=(30, 30, 30))

def process_and_add_text(image, text):
    # 1. പോസ്റ്റർ സൈസിലേക്ക് മാറ്റുന്നു (1080x1080 Square)
    target_size = 1080
    img_w, img_h = image.size
    aspect = img_w / float(img_h)
    
    if aspect > 1: # Landscape
        new_h = target_size
        new_w = int(aspect * new_h)
        image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - target_size) / 2
        image = image.crop((left, 0, left + target_size, target_size))
    else: # Portrait or Square
        new_w = target_size
        new_h = int(target_size / aspect)
        image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - target_size) / 2
        image = image.crop((0, top, target_size, top + target_size))

    # 2. ബാക്ക്ഗ്രൗണ്ട് അല്പം ഡാർക്ക് ആക്കുന്നു (ടെക്സ്റ്റ് കൂടുതൽ വ്യക്തമാകാൻ)
    image = image.convert("RGBA")
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 120)) # പകുതി കറുപ്പ്
    image = Image.alpha_composite(image, overlay)
    
    image = image.convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)
    
    font_path = "MalayalamFont.ttf"
    try:
        font = ImageFont.truetype(font_path, int(width/15))
    except Exception as e:
        font = ImageFont.load_default()
        
    margin = 50
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
            text_w = font.getlength(test_line)
            
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
        line_height = int(width/15)
        
    line_spacing = 35 
    total_text_height = (len(lines) * line_height) + ((len(lines) - 1) * line_spacing)
    y_text = (height - total_text_height) // 2  # ടെക്സ്റ്റ് മധ്യഭാഗത്തായി വെക്കുന്നു
    
    # 3. വർണ്ണാഭമായ ബാക്ക്ഗ്രൗണ്ട് ബോക്സുകളുടെ ഡിസൈൻ
    # ചുവപ്പ്, മഞ്ഞ, നീല, കറുപ്പ് നിറങ്ങൾ
    bg_colors = [(211, 47, 47), (255, 193, 7), (13, 71, 161), (33, 33, 33)]
    text_colors = [(255, 255, 255), (0, 0, 0), (255, 255, 255), (255, 255, 255)] # മഞ്ഞയ്ക്ക് മാത്രം കറുത്ത അക്ഷരങ്ങൾ
    
    for i, line in enumerate(lines):
        color_idx = i % len(bg_colors)
        box_color = bg_colors[color_idx]
        txt_color = text_colors[color_idx]
        
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
        except:
            text_w = font.getlength(line)
            
        x_text = (width - text_w) / 2
        
        # ടെക്സ്റ്റിന് പിന്നിൽ കളർ ബോക്സ് വരയ്ക്കുന്നു
        padding_x = 30
        padding_y = 15
        
        draw.rectangle(
            [x_text - padding_x, y_text - padding_y, x_text + text_w + padding_x, y_text + line_height + padding_y],
            fill=box_color
        )
        
        # ബോക്സിനുള്ളിൽ ടെക്സ്റ്റ് എഴുതുന്നു
        draw.text((x_text, y_text), line, font=font, fill=txt_color)
        
        y_text += line_height + line_spacing
        
    image_path = "fb_post.jpg"
    image.save(image_path, quality=95)
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
    topics_list = get_trending_topics() 
    
    image_text, caption, search_query = get_post_content(topics_list)
    
    if image_text and caption and search_query:
        print("\nചിത്രത്തിലെ ടെക്സ്റ്റ്:", image_text)
        img = fetch_image(search_query)
        final_img = process_and_add_text(img, image_text)
        res = post_to_facebook(final_img, caption)
        print("ഫേസ്ബുക്ക് മറുപടി:", res)
    else:
        print("പോസ്റ്റ് തയ്യാറാക്കാൻ കഴിഞ്ഞില്ല.")

if __name__ == "__main__":
    main()
