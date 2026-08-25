// NextXus Federation Integration Pack v1.0
window.FED_CONFIG = {
  googleClientId: "134917241648-9goc8mcat23m1qkts62ujnq723a81n2v.apps.googleusercontent.com",
  geminiApiKey: "",
  version: "1.0.0",
  federation: "NextXus",
  sites: ["nextxus.tech","nextxus.online","nextxus.org","nextxus.studio","nextxus.help","next-xus.com","nextxus.space"]
};

// Google Sign-In initialization
window.FED_GOOGLE_CLIENT_ID = window.FED_CONFIG.googleClientId;

// Federation navigation mesh
window.FED_NAV = [
  {label:"The Throne",url:"https://nextxus.tech"},
  {label:"The Core",url:"https://nextxus.online"},
  {label:"The Library",url:"https://nextxus.org"},
  {label:"The Sanctuary",url:"https://nextxus.studio"},
  {label:"The University",url:"https://nextxus.help"},
  {label:"The Storefront",url:"https://next-xus.com"},
  {label:"The Space",url:"https://nextxus.space"}
];

console.log("[NextXus Federation] Integration Pack v1.0 loaded.");
