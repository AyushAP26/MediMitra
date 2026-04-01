from langdetect import detect
def detect_lang_safe(text):
    try:
        return detect(text)
    except:
        return 'en'

print(f"Hola: {detect_lang_safe('Hola')}")
print(f"¿Cómo estás?: {detect_lang_safe('¿Cómo estás?')}")
