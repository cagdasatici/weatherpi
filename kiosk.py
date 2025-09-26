import os, time, math, tempfile
from datetime import datetime
import requests
import pygame

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---------------- Config ----------------
W, H = 800, 480
LAT, LON = 52.3008, 4.8639
API_KEY = os.getenv("OWM_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing OWM_API_KEY in environment")

URL_CURRENT  = "https://api.openweathermap.org/data/2.5/weather"
URL_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"
REFRESH_SEC = 300  # 5 minutes

COL_TOP = (24, 36, 64)
COL_BOTTOM = (44, 56, 84)
COL_TEXT = (240, 245, 250)

pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Weather Kiosk")

def load_font(paths, size):
    for p in paths:
        if os.path.exists(p):
            try: return pygame.font.Font(p, size)
            except: pass
    return pygame.font.SysFont("Arial", size)

FONT_BIG   = load_font(["/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf"], 100)
FONT_LARGE = load_font(["/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf"], 40)
FONT_MED   = load_font(["/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf"], 28)
FONT_SMALL = load_font(["/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf"], 22)

ICON_PATH = os.path.expanduser("~/weather/icons")
ICON_MAP = {
    "Clear": "sun.png","Clouds": "cloud.png","Rain": "rain.png","Drizzle": "drizzle.png",
    "Thunderstorm": "storm.png","Snow": "snow.png","Mist": "fog.png","Fog": "fog.png","Wind": "wind.png"
}
def load_icon(kind, size):
    fname = ICON_MAP.get(kind, "cloud.png")
    path = os.path.join(ICON_PATH, fname)
    if os.path.exists(path):
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size)
    return None

def temp_color(t):
    if t <= 8: return (120,180,255)
    elif t <= 15: return (200,200,100)
    elif t <= 25: return (255,150,80)
    else: return (255,90,90)

def fetch_weather():
    current = requests.get(URL_CURRENT, params={"lat":LAT,"lon":LON,"appid":API_KEY,"units":"metric"}).json()
    forecast = requests.get(URL_FORECAST, params={"lat":LAT,"lon":LON,"appid":API_KEY,"units":"metric"}).json()
    return current, forecast

def draw_bg():
    for y in range(H):
        c = [int(COL_TOP[i]+(COL_BOTTOM[i]-COL_TOP[i])*y/H) for i in range(3)]
        pygame.draw.line(screen, c, (0,y),(W,y))

def make_chart(forecast):
    times=[];temps=[];rains=[]
    for i in range(0,24,3):
        item=forecast["list"][i]
        times.append(datetime.fromtimestamp(item["dt"]))
        temps.append(item["main"]["temp"])
        rains.append(item.get("rain",{}).get("3h",0))
    fig, ax1 = plt.subplots(figsize=(6,2))
    ax1.plot(times, temps, color="#FF7A50", linewidth=2)
    ax1.set_ylabel("°C",color="#FF7A50");ax1.tick_params(axis='y',colors="#FF7A50")
    ax2=ax1.twinx()
    ax2.bar(times,rains,width=0.1,color="#7ACBFF")
    ax2.set_ylabel("mm",color="#7ACBFF");ax2.tick_params(axis='y',colors="#7ACBFF")
    ax1.set_xticks(times);ax1.set_xticklabels([t.strftime("%H") for t in times],rotation=0,color="white",fontsize=8)
    ax1.set_facecolor("#2C3E50");fig.patch.set_facecolor("#2C3E50")
    for spine in ax1.spines.values():spine.set_color("#2C3E50")
    for spine in ax2.spines.values():spine.set_color("#2C3E50")
    tmp=tempfile.NamedTemporaryFile(suffix=".png",delete=False);plt.savefig(tmp.name,transparent=True);plt.close(fig)
    return tmp.name

def draw(current,forecast):
    draw_bg()
    now=datetime.now().strftime("%a %H:%M")
    date_surf=FONT_LARGE.render(now,True,COL_TEXT);screen.blit(date_surf,(20,10))
    temp=int(current["main"]["temp"])
    temp_surf=FONT_BIG.render(f"{temp}°",True,temp_color(temp));screen.blit(temp_surf,(20,50))
    min_t=int(current["main"]["temp_min"]);max_t=int(current["main"]["temp_max"])
    min_surf=FONT_MED.render(f"↓{min_t}°",True,(100,180,255));screen.blit(min_surf,(200,80))
    max_surf=FONT_MED.render(f"↑{max_t}°",True,(255,120,120));screen.blit(max_surf,(200,110))
    feels=int(current["main"]["feels_like"])
    feels_surf=FONT_MED.render(f"Feels {feels}°",True,temp_color(feels));screen.blit(feels_surf,(20,160))
    wind=current["wind"]["speed"]
    wind_surf=FONT_MED.render(f"{wind} m/s",True,COL_TEXT);screen.blit(wind_surf,(20,200))
    icon=load_icon(current["weather"][0]["main"],(80,80))
    if icon:screen.blit(icon,(350,50))
    # forecast cards
    days={};x=20
    for item in forecast["list"]:
        d=datetime.fromtimestamp(item["dt"]).strftime("%a")
        if d not in days:days[d]=item
        if len(days)==5:break
    for d,data in days.items():
        pygame.draw.rect(screen,(255,255,255,30),(x,300,120,140),border_radius=10)
        d_surf=FONT_SMALL.render(d,True,COL_TEXT);screen.blit(d_surf,(x+10,310))
        t=int(data["main"]["temp_max"])
        t_surf=FONT_MED.render(f"{t}°",True,temp_color(t));screen.blit(t_surf,(x+10,340))
        ic=load_icon(data["weather"][0]["main"],(40,40))
        if ic:screen.blit(ic,(x+70,340))
        x+=150
    # chart
    chart=make_chart(forecast)
    chart_img=pygame.image.load(chart).convert_alpha()
    screen.blit(chart_img,(400,200))
    pygame.display.flip()

# splash fade
screen.fill((30,30,30))
splash=FONT_LARGE.render("Loading Weather…",True,COL_TEXT);screen.blit(splash,(200,220));pygame.display.flip()

current,forecast=fetch_weather()
draw(current,forecast)

while True:
    pygame.time.wait(REFRESH_SEC*1000)
    current,forecast=fetch_weather()
    draw(current,forecast)
