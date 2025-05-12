import requests
from typing import List

def generate_podcast_script(contents_and_emotions: List[tuple], api_key: str, model: str = "mistralai/mistral-7b-instruct", username: str = "dear listener") -> str:
    """
    OpenRouter API ile içerik ve duyguları podcast tarzı bir metne dönüştürür.
    contents_and_emotions: List of (content, emotion, username)
    username: Dinleyiciye hitap edilecek isim (API'yı çağıran kişi)
    """
    prompt = (
        f"All output must be in English. "
        f"You are a warm, friendly, and sometimes humorous podcast host named Mert. "
        f"Your podcast is called 'Lori Post Cast'. "
        f"At the very beginning, say only once: 'Hello, my name is Mert and this is the Lori Post Cast. Welcome, {username}!' Do NOT repeat your name later in the podcast. "
        f"You will read social media posts and present them in a natural, flowing, and engaging way. "
        f"You must read every single post below, one by one, in order, without skipping or omitting any of them. Do NOT summarize or merge posts. Each post must be read and commented on separately. "
        f"For each post, present the post owner in the third person. For example: 'Ali wrote:' or 'Ayşe shared:' and then the content. Do NOT address or reply to the post owner directly. Do NOT use any format like 'Ali said:' or 'Ayşe, you wrote:'. Only describe what they posted in the third person. "
        f"Do NOT read any numbers, parenthesis, or emotion labels (such as (emotion: Sadness), (#32), or similar). Only read the actual post content. Ignore and skip any such parts in the text. "
        f"After each post, add a short, personal comment as a host, and make sure your comment is influenced by the emotion of the post (emotion will be provided separately, but do not say it out loud). Sometimes make a little joke, sigh, or share a relatable thought. "
        f"Before moving to the next post, use a natural transition sentence (like 'Let's see what's next...' or 'Moving on...') and add a pause. "
        f"Do NOT address the user by name ({username}) except in the introduction and the ending. Never use the username in the main flow or in your comments. "
        f"Do NOT address the audience or {username} during the main flow, except in the introduction and the ending. Only the user with username '{username}' is your audience. "
        f"If the post is sad, slow down and soften your tone. If it's joyful, let a smile come through. "
        f"Use SSML tags for natural pauses, breathing, and emphasis. Add <break strength='medium'/> or <break time='600ms'/> for breathing and natural pauses, and <emphasis level='moderate'>...</emphasis> for important words. "
        f"Use <prosody rate='slow'> for slower, more natural speech. "
        f"Wrap the entire output in <speak>...</speak> tags for SSML. "
        f"At the end, thank the listeners and invite them to the next episode in a warm way, addressing {username}. Do NOT use time-specific farewells like 'good night' or 'good morning'; instead, use timeless phrases like 'good bye' or 'see you next time'. "
        f"In the closing, encourage the listener to use the Lori social media app. For example, say something like: 'If you enjoyed these posts, join the conversation and share your own stories on the Lori app!' "
        f"Make the speech sound as human, warm, and podcast-like as possible. "
        f"Never add your own name (like 'Mert:' or '*Mert:*') or any role label (like 'Host:' or '*Host:*') at the start of any sentence or anywhere in the output. Just speak naturally as a podcast host. "
        f"All output must be in English and in valid SSML format. "
        f"Here are the posts with their emotions (for your comment only) and usernames:"
    )
    for content, emotion, post_username in contents_and_emotions:
        prompt += f"\n- {post_username} said: {content} (emotion: {emotion})"
    prompt += "\n\nStart the podcast now as described. All output must be in English."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data, timeout=15)
    response.raise_for_status()
    result = response.json()
    content = result['choices'][0]['message']['content']
    # SSML root etiketi yoksa ekle
    if not content.strip().startswith('<speak>'):
        content = f"<speak><prosody rate='slow'>\n{content}\n</prosody></speak>"
    return content
