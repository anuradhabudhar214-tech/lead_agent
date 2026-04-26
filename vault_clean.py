class Vault:
    def __init__(self):
        self.config = {}
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                self.config = json.load(f)
        
        serper_env = os.getenv("SERPER_API_KEYS", "") or os.getenv("SERPER_API_KEY", "")
        gemini_env = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
        groq_env = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
        
        self.serper_keys = [k.strip() for k in serper_env.split(",") if k.strip()] or self.config.get("SERPER_API_KEYS", [])
        self.gemini_keys = [k.strip() for k in gemini_env.split(",") if k.strip()] or self.config.get("GEMINI_API_KEYS", [])
        self.groq_keys = [k.strip() for k in groq_env.split(",") if k.strip()] or self.config.get("GROQ_API_KEYS", [])
        
        self.serper_idx = 0
        self.gemini_idx = 0
        self.groq_idx = 0
        self.dead_keys = set()

    def get_serper_key(self):
        if not self.serper_keys: return None
        return self.serper_keys[self.serper_idx % len(self.serper_keys)]
    
    def rotate_serper(self):
        self.serper_idx += 1
        logger.info(f"🔄 Rotated Serper Key")

    def get_gemini_key(self):
        if not self.gemini_keys: return None
        for _ in range(len(self.gemini_keys)):
            key = self.gemini_keys[self.gemini_idx % len(self.gemini_keys)]
            if key not in self.dead_keys: return key
            self.gemini_idx += 1
        return None
