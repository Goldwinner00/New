"""
SHADOWS WITHIN  —  Pygame Survival Horror
WASD=Move  Shift=Sprint  Mouse=Aim  LMB/Space=Attack  M=BigMap  ESC=Pause
"""
import pygame, math, random, sys, heapq
from typing import List

FPS = 60
SCREEN_W, SCREEN_H = 1920, 1080

# ── Colours ───────────────────────────────────────────────────────────────────
BLACK=(0,0,0); WHITE=(255,255,255); RED=(200,20,20); DARK_RED=(120,0,0)
AMBER=(255,180,40); DARK=(15,15,20); BLOOD=(140,0,0); GREEN=(30,180,30)
TEAL=(30,160,130); WALL_C=(45,42,48); WALL_HL=(60,56,65); FLOOR_C=(20,18,22)
CYAN=(40,220,220); ORANGE=(255,120,20); YELLOW=(255,230,60); PURPLE=(160,40,200)

# ── Difficulty settings ───────────────────────────────────────────────────────
DIFF_ROOKIE = 0
DIFF_NORMAL = 1
DIFF_NIGHTMARE = 2

DIFF_SETTINGS = {
    DIFF_ROOKIE: dict(
        name="ROOKIE", color=(60,200,80),
        levers=10,
        monster_chase=1.8, monster_patrol=1.2, monster_dark=3.5,
        battery_max=2400, battery_drain=1,
        stamina_max=420, stamina_drain=1, stamina_regen=1.0, stamina_lock=60,
        num_batteries=10, has_map=True, num_darks=1,
        desc=["Slower Dark","10 levers","More stamina","More batteries"],
    ),
    DIFF_NORMAL: dict(
        name="NORMAL", color=(220,180,30),
        levers=15,
        monster_chase=2.8, monster_patrol=1.8, monster_dark=5.5,
        battery_max=1500, battery_drain=1,
        stamina_max=300, stamina_drain=2, stamina_regen=0.8, stamina_lock=90,
        num_batteries=10, has_map=True, num_darks=2,
        desc=["Standard speed","15 levers","2 Darks hunting you","Normal stamina"],
    ),
    DIFF_NIGHTMARE: dict(
        name="NIGHTMARE", color=(220,30,30),
        levers=20,
        monster_chase=4.2, monster_patrol=2.5, monster_dark=7.0,
        battery_max=900, battery_drain=1,
        stamina_max=380, stamina_drain=2, stamina_regen=1.0, stamina_lock=70,
        num_batteries=8, has_map=False, num_darks=1,
        desc=["Fast Dark","20 levers","NO MAP","Shorter battery"],
    ),
}

# ── Map ───────────────────────────────────────────────────────────────────────
LEVEL_MAP = [
    "111111111111111111111111111111111111111111111",
    "101000100000000010000000000010000000000000001",
    "101010001010111011100011111011111110110111111",
    "101010001010100000000010000000000010000000001",
    "101010101010111001111110100000111010111111101",
    "101000100010000000000010001010100010100000101",
    "100010101100101111111011101010100010100000101",
    "100000100000100000000010001000100010100000101",
    "101110001000101111111110101111001110101010001",
    "101000000000100010100000000000001000001000001",
    "101011101110110010101110001111111010111111101",
    "101000001010000010001010001000100000000000001",
    "101111001010111010011011111001101101111010111",
    "101000000010100010000000100000001000001000001",
    "101111100010101110001110111011111011100011011",
    "100000100000101010100000001000100010001000001",
    "110110100011101010000111101110101110111111101",
    "100010100000001010000010100010000010000000001",
    "111010101111111010111010111011111011111110001",
    "100010101000000000000010001000000010000000101",
    "101110101111111001001100001111110110111011101",
    "101000001000000000000000000000000010101000001",
    "101001101011111010101011110111101010101100111",
    "101000001010000010000010000010000010100000101",
    "101001111000111010111110100010111110111010101",
    "100000100000100010001000101000001000100010101",
    "101011100111101111101011101110111011101110001",
    "101000000000100000000000100000000000001000001",
    "111111111111111111111111111111111111111111111",
]
ROWS_MAP = len(LEVEL_MAP)
COLS_MAP = len(LEVEL_MAP[0])
TILE_W   = SCREEN_W // COLS_MAP
TILE_H   = SCREEN_H // ROWS_MAP

# ── Map helpers ───────────────────────────────────────────────────────────────
def get_walls():
    return [pygame.Rect(c*TILE_W, r*TILE_H, TILE_W, TILE_H)
            for r,row in enumerate(LEVEL_MAP)
            for c,ch in enumerate(row) if ch=='1']

def tile_center(c, r):
    return (c*TILE_W + TILE_W//2, r*TILE_H + TILE_H//2)

def is_floor(c, r):
    if r<=0 or r>=ROWS_MAP-1 or c<=0 or c>=COLS_MAP-1: return False
    return LEVEL_MAP[r][c]=='0'

def safe_floor_tiles():
    return [(c,r) for r in range(1,ROWS_MAP-1) for c in range(1,COLS_MAP-1)
            if LEVEL_MAP[r][c]=='0' and
            any(is_floor(c+dc,r+dr) for dc,dr in[(1,0),(-1,0),(0,1),(0,-1)])]

def world_to_tile(x,y):
    return (int(x//TILE_W), int(y//TILE_H))

# ── Spatial wall index — fast nearby-wall lookup ──────────────────────────────
_WALL_GRID = {}
def _build_wall_grid():
    global _WALL_GRID
    _WALL_GRID = {}
    for r,row in enumerate(LEVEL_MAP):
        for c,ch in enumerate(row):
            if ch=='1':
                _WALL_GRID[(c,r)] = pygame.Rect(c*TILE_W, r*TILE_H, TILE_W, TILE_H)

def get_nearby_walls(x, y, radius_px):
    if not _WALL_GRID: _build_wall_grid()
    cr = int(radius_px // TILE_W) + 1
    cc, rc = int(x // TILE_W), int(y // TILE_H)
    result = []
    for dr in range(-cr, cr+1):
        for dc in range(-cr, cr+1):
            w = _WALL_GRID.get((cc+dc, rc+dr))
            if w: result.append(w)
    return result

# ── A* pathfinding ────────────────────────────────────────────────────────────
def astar(start, goal):
    if start==goal: return [start]
    heap=[(0,start)]; came={start:None}; g={start:0}
    heur=lambda a,b: abs(a[0]-b[0])+abs(a[1]-b[1])
    while heap:
        _,cur=heapq.heappop(heap)
        if cur==goal:
            path=[]; n=cur
            while n: path.append(n); n=came[n]
            path.reverse(); return path
        for dc,dr in[(1,0),(-1,0),(0,1),(0,-1)]:
            nb=(cur[0]+dc,cur[1]+dr)
            if not is_floor(*nb): continue
            ng=g[cur]+1
            if nb not in g or ng<g[nb]:
                g[nb]=ng; came[nb]=cur
                heapq.heappush(heap,(ng+heur(nb,goal),nb))
    return []

# ── Global font cache ─────────────────────────────────────────────────────────
_FONTS = {}
def get_font(size, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        _FONTS[key] = pygame.font.SysFont("courier", size, bold=bold)
    return _FONTS[key]

# ── Sound manager ─────────────────────────────────────────────────────────────
class SoundManager:
    SR = 44100
    def __init__(self):
        try:
            pygame.mixer.init(frequency=self.SR, size=-16, channels=2, buffer=1024)
            self._ok = True
        except Exception:
            self._ok = False; return
        self._vol = 0.8
        self._sounds = {}
        self._ch_drone  = pygame.mixer.Channel(0)
        self._ch_growl  = pygame.mixer.Channel(1)
        self._ch_sfx    = pygame.mixer.Channel(2)
        self._ch_step   = pygame.mixer.Channel(3)
        self._ch_music  = pygame.mixer.Channel(4)
        self._ch_ambient= pygame.mixer.Channel(5)
        self._step_timer= 0
        self._step_foot = False
        self._build_all()

    def _make(self, dur, vol, *partials, noise=0.0, atk=0.02, rel=0.15):
        import array as arr
        n=int(self.SR*dur); atk_n=max(1,int(atk*self.SR)); rel_n=max(1,int(rel*self.SR))
        buf=arr.array('h', bytes(n*4))
        for i in range(n):
            t=i/self.SR
            if i<atk_n:         env=i/atk_n
            elif i>n-rel_n:     env=(n-i)/rel_n
            else:               env=1.0
            s=0.0
            for freq,wave,amp in partials:
                phase=freq*t
                if wave=='sin': s+=amp*math.sin(2*math.pi*phase)
                elif wave=='sqr': s+=amp*(1.0 if math.sin(2*math.pi*phase)>0 else -1.0)
                elif wave=='saw': s+=amp*2.0*(phase-math.floor(phase+0.5))
            if noise>0: s+=noise*random.uniform(-1.0,1.0)
            sample=int(max(-1.0,min(1.0,s))*env*vol*32767)
            buf[i*2]=sample; buf[i*2+1]=sample
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _build_all(self):
        try:
            self._sounds['step_l']=self._make(0.11,0.18,(60,'sin',0.6),(30,'sin',0.4),noise=0.08,atk=0.002,rel=0.09)
            self._sounds['step_r']=self._make(0.11,0.18,(52,'sin',0.6),(26,'sin',0.4),noise=0.08,atk=0.002,rel=0.09)
            self._sounds['lever'] =self._make(0.22,0.32,(180,'sqr',0.6),(90,'sin',0.4),atk=0.005,rel=0.18)
            self._sounds['battery']=self._make(0.30,0.35,(880,'sin',0.5),(1108,'sin',0.3),(660,'sin',0.2),atk=0.01,rel=0.22)
            self._sounds['hurt']  =self._make(0.35,0.50,(100,'sin',0.4),(60,'saw',0.3),noise=0.5,atk=0.005,rel=0.28)
            self._sounds['growl'] =self._make(0.55,0.30,(55,'saw',0.5),(82,'saw',0.3),(41,'sin',0.2),noise=0.1,atk=0.05,rel=0.35)
            self._sounds['win']   =self._make(0.60,0.38,(523,'sin',0.5),(659,'sin',0.35),(784,'sin',0.25),atk=0.02,rel=0.40)
            self._sounds['die']   =self._make(0.75,0.42,(220,'saw',0.5),(110,'saw',0.3),(165,'sin',0.2),noise=0.15,atk=0.01,rel=0.55)
            self._sounds['drone'] =self._make(4.0,0.20,(55,'sin',0.45),(82,'sin',0.30),(110,'sin',0.15),(27,'sin',0.10),noise=0.03,atk=0.5,rel=0.5)
            self._sounds['drone'].set_volume(0.18)
            self._ch_drone.play(self._sounds['drone'],loops=-1)
            self._sounds['scrape']    =self._make(1.2,0.38,(180,'saw',0.35),(90,'saw',0.25),(270,'saw',0.15),noise=0.55,atk=0.12,rel=0.55)
            self._sounds['ghost_step']=self._make(0.55,0.30,(48,'sin',0.5),(32,'sin',0.35),(72,'sin',0.15),noise=0.20,atk=0.01,rel=0.45)
            self._sounds['door_slam'] =self._make(0.80,0.55,(65,'sqr',0.50),(40,'saw',0.30),(130,'sin',0.20),noise=0.35,atk=0.003,rel=0.65)
            import array as arr2
            SR=self.SR; DUR=8.0; N=int(SR*DUR)
            buf2=arr2.array('h',bytes(N*4))
            melody=[130.8,123.5,116.5,110.0,103.8,98.0,103.8,110.0]
            note_len=N//len(melody)
            for i in range(N):
                t=i/SR; ni=min(i//note_len,len(melody)-1); mf=melody[ni]
                bass_env=max(0.0,1.0-((t%1.0)*2.2))
                bass=math.sin(2*math.pi*55*t)*0.35*bass_env+math.sin(2*math.pi*27.5*t)*0.18*bass_env
                trem=0.5+0.5*math.sin(2*math.pi*4.5*t)
                pad=math.sin(2*math.pi*mf*t)*0.20*trem+math.sin(2*math.pi*mf*1.5*t)*0.08*trem
                whisper=random.uniform(-1,1)*0.04
                boundary=min(i,N-i); fade=min(1.0,boundary/(SR*0.3))
                s=max(-1.0,min(1.0,(bass+pad+whisper)*fade))
                v=int(s*0.28*32767); buf2[i*2]=v; buf2[i*2+1]=v
            music_snd=pygame.mixer.Sound(buffer=bytes(buf2))
            music_snd.set_volume(0.22)
            self._sounds['music']=music_snd
            self._ch_music.play(music_snd,loops=-1)
        except Exception:
            self._ok=False

    def set_master_volume(self,v):
        self._vol=max(0.0,min(1.0,v))
        if not self._ok: return
        self._ch_drone.set_volume(self._vol*0.18)
        if 'music' in self._sounds: self._ch_music.set_volume(self._vol*0.22)

    def play(self,name,base_vol=0.35):
        if not self._ok: return
        snd=self._sounds.get(name)
        if not snd: return
        snd.set_volume(self._vol*base_vol)
        self._ch_sfx.play(snd)

    def play_growl(self):
        if not self._ok: return
        if not self._ch_growl.get_busy():
            self._sounds['growl'].set_volume(self._vol*0.28)
            self._ch_growl.play(self._sounds['growl'])

    def maybe_step(self,moving,sprinting=False):
        if not self._ok or not moving: return
        self._step_timer-=1
        interval=12 if sprinting else 22
        if self._step_timer<=0:
            self._step_timer=interval; self._step_foot=not self._step_foot
            snd=self._sounds['step_l'] if self._step_foot else self._sounds['step_r']
            snd.set_volume(self._vol*(0.28 if sprinting else 0.22))
            self._ch_step.play(snd)

    def play_ambient(self,name):
        if not self._ok: return
        snd=self._sounds.get(name)
        if snd and not self._ch_ambient.get_busy():
            snd.set_volume(self._vol*random.uniform(0.25,0.55))
            self._ch_ambient.play(snd)

    def set_drone_volume(self,vol):
        if not self._ok: return
        self._ch_drone.set_volume(self._vol*max(0.0,min(1.0,vol)))

# ── Flashlight ────────────────────────────────────────────────────────────────
def cast_flashlight(pos, angle, fov_deg, walls, length=300, rays=48):
    nearby=get_nearby_walls(pos[0],pos[1],length+TILE_W)
    half=math.radians(fov_deg/2); pts=[pos]
    for i in range(rays+1):
        a=angle-half+(2*half*i/rays)
        cdx,cdy=math.cos(a),math.sin(a); best=length
        for w in nearby:
            tx1=(w.left-pos[0])/cdx   if cdx else 1e9
            tx2=(w.right-pos[0])/cdx  if cdx else 1e9
            ty1=(w.top-pos[1])/cdy    if cdy else 1e9
            ty2=(w.bottom-pos[1])/cdy if cdy else 1e9
            tmin=max(min(tx1,tx2),min(ty1,ty2)); tmax=min(max(tx1,tx2),max(ty1,ty2))
            if 0<tmin<tmax and tmin<best: best=tmin
        pts.append((pos[0]+cdx*best,pos[1]+cdy*best))
    return pts

def point_in_poly(x,y,poly):
    inside=False; j=len(poly)-1
    for i in range(len(poly)):
        xi,yi=poly[i]; xj,yj=poly[j]
        if ((yi>y)!=(yj>y)) and (x<(xj-xi)*(y-yi)/(yj-yi)+xi): inside=not inside
        j=i
    return inside

# ── Particle ──────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self,x,y,color,vx=None,vy=None,life=None,size=None):
        self.x,self.y=x,y; self.color=color
        self.vx=vx if vx is not None else random.uniform(-2.5,2.5)
        self.vy=vy if vy is not None else random.uniform(-3,.5)
        self.life=life if life is not None else random.randint(20,50)
        self.max_life=self.life
        self.size=size if size is not None else random.randint(2,5)
    def update(self): self.x+=self.vx; self.y+=self.vy; self.vy+=.12; self.life-=1
    def draw(self,surf):
        a=self.life/self.max_life
        c=(int(self.color[0]*a),int(self.color[1]*a),int(self.color[2]*a))
        pygame.draw.circle(surf,c,(int(self.x),int(self.y)),max(1,int(self.size*a)))
    def alive(self): return self.life>0

# ── Player ────────────────────────────────────────────────────────────────────
class Player:
    WALK_SPEED=3.0; SPRINT_SPEED=5.2
    RADIUS=10; MAX_HP=5; ATTACK_RANGE=55; ATTACK_CD=40

    def __init__(self,x,y,diff):
        self.x,self.y=float(x),float(y); self.hp=self.MAX_HP
        self.attack_timer=0; self.hurt_timer=0; self.levers=0
        d=DIFF_SETTINGS[diff]
        self.STAMINA_MAX=d['stamina_max']; self.STAMINA_DRAIN=d['stamina_drain']
        self.STAMINA_REGEN=d['stamina_regen']; self.STAMINA_LOCK=d['stamina_lock']
        self.BATTERY_MAX=d['battery_max']; self.BATTERY_DRAIN=d['battery_drain']
        self.stamina=float(self.STAMINA_MAX); self.stamina_locked=0
        self.is_sprinting=False
        self.battery=float(self.BATTERY_MAX); self.battery_dead=False
        self.fx_strobe=0; self.fx_overcharge=0; self.fx_adrenaline=0; self.fx_cloak=0
        self.has_flare=False; self.has_trap=False

    @property
    def pos(self): return (int(self.x),int(self.y))
    @property
    def rect(self):
        r=self.RADIUS; return pygame.Rect(self.x-r,self.y-r,r*2,r*2)

    def move(self,dx,dy,walls,sprinting):
        moving=bool(dx or dy)
        if sprinting and moving and self.stamina>0 and self.stamina_locked==0:
            self.is_sprinting=True
            self.stamina=max(0,self.stamina-self.STAMINA_DRAIN)
            if self.stamina==0: self.stamina_locked=self.STAMINA_LOCK
        else:
            self.is_sprinting=False
            self.stamina=min(self.STAMINA_MAX,
                self.stamina+(self.STAMINA_REGEN if moving else self.STAMINA_REGEN*2))
        if self.stamina_locked>0: self.stamina_locked-=1
        speed=self.SPRINT_SPEED if self.is_sprinting else self.WALK_SPEED
        if dx and dy: dx*=.707; dy*=.707
        dx*=speed; dy*=speed
        nearby=get_nearby_walls(self.x,self.y,self.RADIUS*4)
        self.x+=dx
        for w in nearby:
            if self.rect.colliderect(w):
                self.x=(w.left-self.RADIUS) if dx>0 else (w.right+self.RADIUS)
        self.y+=dy
        for w in nearby:
            if self.rect.colliderect(w):
                self.y=(w.top-self.RADIUS) if dy>0 else (w.bottom+self.RADIUS)
        return moving

    def drain_battery(self):
        if self.battery>0:
            self.battery=max(0,self.battery-self.BATTERY_DRAIN)
            if self.battery==0 and not self.battery_dead: self.battery_dead=True

    def recharge(self,amount):
        self.battery=min(self.BATTERY_MAX,self.battery+amount)
        self.battery_dead=(self.battery==0)

    def try_attack(self,enemy):
        if self.attack_timer>0: return False
        if math.hypot(enemy.x-self.x,enemy.y-self.y)<self.ATTACK_RANGE:
            self.attack_timer=self.ATTACK_CD; return True
        return False

    def take_damage(self):
        if self.hurt_timer>0: return
        self.hp-=1; self.hurt_timer=80

    def update(self):
        if self.attack_timer>0: self.attack_timer-=1
        if self.hurt_timer>0:   self.hurt_timer-=1

    def draw(self,surf,fl_angle):
        col=RED if self.hurt_timer>0 and self.hurt_timer%6<3 else AMBER
        if self.is_sprinting: pygame.draw.circle(surf,(60,30,0),self.pos,self.RADIUS+5)
        pygame.draw.circle(surf,(int(col[0]*.4),int(col[1]*.4),0),self.pos,self.RADIUS+3)
        pygame.draw.circle(surf,col,self.pos,self.RADIUS)
        ex=int(self.x+math.cos(fl_angle)*6); ey=int(self.y+math.sin(fl_angle)*6)
        pygame.draw.circle(surf,WHITE,(ex,ey),3)

# ── Monster ───────────────────────────────────────────────────────────────────
class Monster:
    RADIUS=15; MAX_HP=8; ATTACK_RANGE=24; ATTACK_CD=75
    HEAR_RANGE=150; SEARCH_SPEED=2.0; PATH_REFRESH=30

    def __init__(self,x,y,diff):
        self.x,self.y=float(x),float(y); self.hp=self.MAX_HP
        self.mode='patrol'; self.patrol_target=(x,y); self.patrol_timer=0
        self.search_timer=0; self.attack_timer=0; self.hurt_timer=0
        self.last_known=None; self.angle=random.uniform(0,math.pi*2)
        self.path=[]; self.path_timer=0; self.stun_timer=0
        d=DIFF_SETTINGS[diff]
        self.CHASE_SPEED=d['monster_chase']
        self.PATROL_SPEED=d['monster_patrol']
        self.DARK_SPEED=d['monster_dark']

    @property
    def pos(self): return (int(self.x),int(self.y))
    @property
    def rect(self):
        r=self.RADIUS; return pygame.Rect(self.x-r,self.y-r,r*2,r*2)

    def new_patrol(self,floors,ppos=None):
        if ppos and random.random()<0.75:
            px,py=ppos
            near=[f for f in floors
                  if abs(tile_center(*f)[0]-px)<SCREEN_W*0.6
                  and abs(tile_center(*f)[1]-py)<SCREEN_H*0.6]
            if near:
                self.patrol_target=tile_center(*random.choice(near))
                self.patrol_timer=random.randint(40,120); return
        self.patrol_target=tile_center(*random.choice(floors))
        self.patrol_timer=random.randint(60,160)

    def _refresh_path(self,tx,ty):
        start=world_to_tile(self.x,self.y); goal=world_to_tile(tx,ty)
        self.path=astar(start,goal)
        if self.path and self.path[0]==start: self.path.pop(0)
        self.path_timer=self.PATH_REFRESH

    def _move_along_path(self,speed,walls):
        while self.path:
            wx,wy=tile_center(*self.path[0])
            if math.hypot(wx-self.x,wy-self.y)<max(TILE_W,TILE_H)*0.6: self.path.pop(0)
            else: break
        if not self.path: return
        wx,wy=tile_center(*self.path[0])
        dx=wx-self.x; dy=wy-self.y; dist=math.hypot(dx,dy)
        if dist<2: return
        self.angle=math.atan2(dy,dx)
        nx,ny=dx/dist*speed,dy/dist*speed
        nearby=get_nearby_walls(self.x,self.y,self.RADIUS*3)
        self.x+=nx
        for w in nearby:
            if self.rect.colliderect(w):
                self.x=w.left-self.RADIUS if nx>0 else w.right+self.RADIUS
        self.y+=ny
        for w in nearby:
            if self.rect.colliderect(w):
                self.y=w.top-self.RADIUS if ny>0 else w.bottom+self.RADIUS

    def update(self,player,walls,floors,in_fl,battery_dead,cloaked=False):
        if self.attack_timer>0: self.attack_timer-=1
        if self.hurt_timer>0:   self.hurt_timer-=1
        if self.stun_timer>0:
            self.stun_timer-=1; return
        self.path_timer=max(0,self.path_timer-1)
        dist_p=math.hypot(player.x-self.x,player.y-self.y)
        if cloaked:
            can_detect=False
            if self.mode=='chase':
                self.mode='search'; self.search_timer=random.randint(120,200)
        else:
            can_detect=(dist_p<self.HEAR_RANGE or in_fl or battery_dead)
        if can_detect:
            self.mode='chase'; self.last_known=(player.x,player.y); self.search_timer=600
        spd=self.DARK_SPEED if battery_dead else self.CHASE_SPEED
        if self.mode=='chase':
            tx,ty=player.x,player.y
            if not can_detect:
                self.search_timer-=1
                if self.search_timer<=0:
                    self.mode='search'; self.search_timer=random.randint(240,420)
            if self.path_timer==0: self._refresh_path(tx,ty)
            if not self.path and self.last_known:
                lx,ly=self.last_known; d=math.hypot(lx-self.x,ly-self.y)
                if d>2:
                    self.x+=((lx-self.x)/d)*spd; self.y+=((ly-self.y)/d)*spd
        elif self.mode=='search' and self.last_known:
            spd=self.SEARCH_SPEED; tx,ty=self.last_known
            self.search_timer-=1
            if self.search_timer<=0: self.mode='patrol'
            if self.path_timer==0: self._refresh_path(tx,ty)
        else:
            self.mode='patrol'; spd=self.PATROL_SPEED
            tx,ty=self.patrol_target; self.patrol_timer-=1
            if self.patrol_timer<=0 or math.hypot(tx-self.x,ty-self.y)<10:
                self.new_patrol(floors,(player.x,player.y)); self.path=[]
            if self.path_timer==0: self._refresh_path(tx,ty)
        self._move_along_path(spd,walls)
        if dist_p<self.ATTACK_RANGE and self.attack_timer==0:
            player.take_damage(); self.attack_timer=self.ATTACK_CD

    def take_hit(self): self.hp-=1; self.hurt_timer=20

    def draw(self,surf,in_fl):
        chasing=self.mode=='chase'
        if not in_fl:
            if chasing:
                gr=self.RADIUS+6+int(math.sin(pygame.time.get_ticks()*.01)*3)
                pygame.draw.circle(surf,(50,0,0),self.pos,gr)
                for s in[-1,1]:
                    ex=int(self.x+math.cos(self.angle)*7+math.sin(self.angle)*5*s)
                    ey=int(self.y+math.sin(self.angle)*7-math.cos(self.angle)*5*s)
                    pygame.draw.circle(surf,RED,(ex,ey),4)
                    pygame.draw.circle(surf,(255,120,120),(ex,ey),2)
            return
        flicker=self.hurt_timer>0 and self.hurt_timer%4<2
        body=(20,5,5) if flicker else (45,10,10)
        pygame.draw.circle(surf,(70,15,15),self.pos,self.RADIUS+3)
        pygame.draw.circle(surf,body,self.pos,self.RADIUS)
        t=pygame.time.get_ticks()
        for i in range(8):
            a=self.angle+i*math.pi/4+t*.001
            pygame.draw.line(surf,(60,0,0),self.pos,
                (int(self.x+math.cos(a)*(self.RADIUS+5)),int(self.y+math.sin(a)*(self.RADIUS+5))),1)
        for s in[-1,1]:
            ex=int(self.x+math.cos(self.angle)*7+math.sin(self.angle)*5*s)
            ey=int(self.y+math.sin(self.angle)*7-math.cos(self.angle)*5*s)
            pygame.draw.circle(surf,RED,(ex,ey),4)
            pygame.draw.circle(surf,(255,100,100),(ex,ey),2)
        bw=32; filled=int(bw*self.hp/self.MAX_HP)
        bx,by=int(self.x-bw//2),int(self.y-self.RADIUS-9)
        pygame.draw.rect(surf,DARK_RED,(bx,by,bw,4))
        pygame.draw.rect(surf,RED,(bx,by,filled,4))

# ── Lever ─────────────────────────────────────────────────────────────────────
class Lever:
    def __init__(self,x,y):
        self.x,self.y=int(x),int(y); self.collected=False
        self.bob=random.uniform(0,math.pi*2); self.pulse=random.uniform(0,math.pi*2)
    def update(self): self.bob+=.05; self.pulse+=.08
    def draw(self,surf):
        if self.collected: return
        cy=int(self.y+math.sin(self.bob)*4); cx=self.x
        gr=int(16+math.sin(self.pulse)*4)
        if not hasattr(self,'_glow') or self._glow_r!=gr:
            self._glow=pygame.Surface((gr*2+4,gr*2+4),pygame.SRCALPHA)
            self._glow.fill((0,0,0,0))
            pygame.draw.circle(self._glow,(255,200,40,50),(gr+2,gr+2),gr)
            self._glow_r=gr
        surf.blit(self._glow,(cx-gr-2,cy-gr-2))
        pygame.draw.rect(surf,(100,80,20),(cx-3,cy-8,6,14),border_radius=2)
        pygame.draw.circle(surf,AMBER,(cx,cy-8),5)
        pygame.draw.circle(surf,WHITE,(cx,cy-8),2)
        pygame.draw.rect(surf,(140,110,30),(cx-7,cy+4,14,5),border_radius=2)
    def check_collect(self,player):
        if self.collected: return False
        if math.hypot(self.x-player.x,self.y-player.y)<22:
            self.collected=True; return True
        return False

# ── Battery ───────────────────────────────────────────────────────────────────
class Battery:
    RECHARGE=1800
    def __init__(self,x,y):
        self.x,self.y=int(x),int(y); self.collected=False
        self.pulse=random.uniform(0,math.pi*2)
    def update(self): self.pulse+=.06
    def draw(self,surf):
        if self.collected: return
        cx,cy=self.x,self.y; gr=int(14+math.sin(self.pulse)*4)
        if not hasattr(self,'_glow') or self._glow_r!=gr:
            self._glow=pygame.Surface((gr*2+4,gr*2+4),pygame.SRCALPHA)
            self._glow.fill((0,0,0,0))
            pygame.draw.circle(self._glow,(40,220,220,45),(gr+2,gr+2),gr)
            self._glow_r=gr
        surf.blit(self._glow,(cx-gr-2,cy-gr-2))
        pygame.draw.rect(surf,(20,80,90),(cx-7,cy-5,14,10),border_radius=2)
        pygame.draw.rect(surf,CYAN,(cx-6,cy-4,12,8),border_radius=1)
        pygame.draw.rect(surf,CYAN,(cx+7,cy-2,3,4),border_radius=1)
        f=get_font(9,bold=True)
        t=f.render("+",True,WHITE); surf.blit(t,(cx-t.get_width()//2,cy-t.get_height()//2))
    def check_collect(self,player):
        if self.collected: return False
        if math.hypot(self.x-player.x,self.y-player.y)<22:
            self.collected=True; return True
        return False

# ── Powerups ──────────────────────────────────────────────────────────────────
POWERUP_TYPES=['strobe','overcharge','adrenaline','cloak','flare','medkit','trap']
POWERUP_CFG={
    'strobe':     dict(color=(180,220,255),label="STROBE",     duration=8*60),
    'overcharge': dict(color=(255,240,80), label="OVERCHARGE", duration=10*60),
    'adrenaline': dict(color=(255,120,20), label="ADRENALINE", duration=10*60),
    'cloak':      dict(color=(140,60,220), label="SHADOW CLOAK",duration=8*60),
    'flare':      dict(color=(255,80,20),  label="FLARE",      duration=0),
    'medkit':     dict(color=(60,220,80),  label="MED KIT",    duration=0),
    'trap':       dict(color=(200,160,40), label="TRAP",       duration=0),
}

class Powerup:
    RADIUS=20; COLLECT_R=26
    def __init__(self,x,y,kind):
        self.x,self.y=int(x),int(y); self.kind=kind; self.collected=False
        self.bob=random.uniform(0,math.pi*2); self.pulse=random.uniform(0,math.pi*2)
        self.cfg=POWERUP_CFG[kind]
    def update(self): self.bob+=.04; self.pulse+=.07
    def draw(self,surf):
        if self.collected: return
        col=self.cfg['color']
        cy=int(self.y+math.sin(self.bob)*5); cx=self.x
        gr=int(18+math.sin(self.pulse)*5)
        if not hasattr(self,'_glow') or self._glow_r!=gr:
            self._glow=pygame.Surface((gr*2+6,gr*2+6),pygame.SRCALPHA)
            self._glow.fill((0,0,0,0))
            pygame.draw.circle(self._glow,(*col,45),(gr+3,gr+3),gr)
            self._glow_r=gr
        surf.blit(self._glow,(cx-gr-3,cy-gr-3))
        pygame.draw.circle(surf,(min(255,col[0]//2),min(255,col[1]//2),min(255,col[2]//2)),(cx,cy),14)
        pygame.draw.circle(surf,col,(cx,cy),11)
        icons={'strobe':'~','overcharge':'!','adrenaline':'>','cloak':'*','flare':'F','medkit':'+','trap':'X'}
        f=get_font(13,bold=True)
        ic=f.render(icons.get(self.kind,'?'),True,(0,0,0))
        surf.blit(ic,(cx-ic.get_width()//2,cy-ic.get_height()//2))
        lf=get_font(10,bold=True)
        lt=lf.render(self.cfg['label'],True,col)
        surf.blit(lt,(cx-lt.get_width()//2,cy+15))
    def check_collect(self,player):
        if self.collected: return False
        if math.hypot(self.x-player.x,self.y-player.y)<self.COLLECT_R:
            self.collected=True; return True
        return False

class PlacedTrap:
    RADIUS=18; TRIGGER_R=22
    def __init__(self,x,y):
        self.x,self.y=int(x),int(y); self.triggered=False; self.stun_timer=0; self.anim=0
    def update(self,darks):
        self.anim+=0.08
        if self.triggered: self.stun_timer=max(0,self.stun_timer-1); return
        for dk in darks:
            if math.hypot(dk.x-self.x,dk.y-self.y)<self.TRIGGER_R:
                self.triggered=True; self.stun_timer=5*60; dk.stun_timer=5*60
    def draw(self,surf):
        if self.triggered and self.stun_timer<=0: return
        col=(200,160,40) if not self.triggered else (255,80,20)
        pulse=int(12+math.sin(self.anim)*4)
        pygame.draw.circle(surf,(col[0]//3,col[1]//3,0),(self.x,self.y),pulse+3)
        pygame.draw.circle(surf,col,(self.x,self.y),8,2)
        pygame.draw.line(surf,col,(self.x-8,self.y),(self.x+8,self.y),2)
        pygame.draw.line(surf,col,(self.x,self.y-8),(self.x,self.y+8),2)
    def alive(self): return not self.triggered or self.stun_timer>0

class ActiveFlare:
    ATTRACT_R=300; LIFETIME=10*60
    def __init__(self,x,y):
        self.x,self.y=int(x),int(y); self.timer=self.LIFETIME; self.anim=0
    def update(self): self.timer-=1; self.anim+=0.15
    def draw(self,surf):
        if self.timer<=0: return
        fade=min(1.0,self.timer/60); r=int(255*fade); col=(r,int(r*0.4),0)
        gr=int(20+math.sin(self.anim)*8)
        if not hasattr(self,'_glow') or self._glow_r!=gr:
            self._glow=pygame.Surface((gr*2+6,gr*2+6),pygame.SRCALPHA); self._glow_r=gr
        self._glow.fill((0,0,0,0))
        pygame.draw.circle(self._glow,(*col,int(80*fade)),(gr+3,gr+3),gr)
        surf.blit(self._glow,(self.x-gr-3,self.y-gr-3))
        pygame.draw.circle(surf,col,(self.x,self.y),6)
        pygame.draw.circle(surf,(255,220,100),(self.x,self.y),3)
    def alive(self): return self.timer>0

# ── Minimap ───────────────────────────────────────────────────────────────────
MMAP_SCALE=6
MMAP_SCALE_BIG=14

def draw_minimap(surf,player,levers,batteries,exit_pos,darks,total_levers,sfont,big=False,mm_static=None,mm_static_big=None):
    BW=52; PAD=8
    sc=MMAP_SCALE_BIG if big else MMAP_SCALE
    mw=COLS_MAP*sc; mh=ROWS_MAP*sc
    if big:
        mx0=SCREEN_W//2-mw//2; my0=SCREEN_H//2-mh//2
    else:
        mx0=SCREEN_W-BW-PAD-mw; my0=BW+PAD+18

    # Item-layer cache — only rebuilt when collectables change
    levers_left=sum(1 for lv in levers if not lv.collected)
    batts_left=sum(1 for b in batteries if not b.collected)
    levers_done=player.levers>=total_levers
    cache_key=(big,levers_left,batts_left,levers_done)
    c_surf='_mm_cache_big' if big else '_mm_cache'
    c_key ='_mm_ckey_big'  if big else '_mm_ckey'
    baked =mm_static_big if big else mm_static

    if getattr(draw_minimap,c_key,None)!=cache_key or \
       getattr(draw_minimap,c_surf,pygame.Surface((1,1))).get_size()!=(mw,mh):
        item_surf=baked.copy() if baked else pygame.Surface((mw,mh),pygame.SRCALPHA)
        if not baked:
            item_surf.fill((0,0,0,200 if big else 160))
            for r,row in enumerate(LEVEL_MAP):
                for c,ch in enumerate(row):
                    col2=(70,65,80,220) if ch=='1' else (30,28,35,180)
                    pygame.draw.rect(item_surf,col2,(c*sc,r*sc,sc,sc))
        if levers_done:
            ex_mm=int(exit_pos[0]/TILE_W*sc); ey_mm=int(exit_pos[1]/TILE_H*sc)
            pygame.draw.circle(item_surf,GREEN,(ex_mm,ey_mm),max(4,sc//3))
        for lv in levers:
            if not lv.collected:
                lx=int(lv.x/TILE_W*sc); ly=int(lv.y/TILE_H*sc)
                pygame.draw.circle(item_surf,AMBER,(lx,ly),max(3,sc//4))
        for b in batteries:
            if not b.collected:
                bx2=int(b.x/TILE_W*sc); by2=int(b.y/TILE_H*sc)
                pygame.draw.circle(item_surf,CYAN,(bx2,by2),max(3,sc//4))
        setattr(draw_minimap,c_surf,item_surf)
        setattr(draw_minimap,c_key,cache_key)

    mm=getattr(draw_minimap,c_surf).copy()

    tick=pygame.time.get_ticks()
    if not hasattr(draw_minimap,'_ping_cache') or draw_minimap._ping_cache.get_size()!=(mw,mh):
        draw_minimap._ping_cache=pygame.Surface((mw,mh),pygame.SRCALPHA)
    ping_surf=draw_minimap._ping_cache; ping_surf.fill((0,0,0,0))
    for dk in darks:
        mx_mm=int(dk.x/TILE_W*sc); my_mm=int(dk.y/TILE_H*sc)
        ping=(tick%1200)/1200.0; ring_r=int(2+ping*12); ring_a=int(255*(1-ping))
        if ring_a>10:
            pygame.draw.circle(ping_surf,(200,0,0,ring_a),(mx_mm,my_mm),ring_r,1)
        pygame.draw.circle(mm,RED if dk.mode=='chase' else (130,25,25),(mx_mm,my_mm),max(3,sc//3))
    mm.blit(ping_surf,(0,0))
    px_mm=int(player.x/TILE_W*sc); py_mm=int(player.y/TILE_H*sc)
    pygame.draw.circle(mm,AMBER,(px_mm,py_mm),max(3,sc//3))

    if big:
        bg=pygame.Surface((mw+20,mh+40),pygame.SRCALPHA)
        bg.fill((0,0,0,160)); surf.blit(bg,(mx0-10,my0-30))
        surf.blit(mm,(mx0,my0))
        pygame.draw.rect(surf,(80,70,60),(mx0-1,my0-1,mw+2,mh+2),2)
        lbl=sfont.render("MAP  [M to close]",True,(120,110,80))
        surf.blit(lbl,(mx0,my0-22))
    else:
        surf.blit(mm,(mx0,my0))
        pygame.draw.rect(surf,(80,70,60),(mx0-1,my0-1,mw+2,mh+2),1)
        surf.blit(sfont.render("MAP [M]",True,(90,80,60)),(mx0,my0-15))

# ── HUD ───────────────────────────────────────────────────────────────────────
def heart_pts(cx,cy,r):
    pts=[]
    for i in range(60):
        t=i/60*math.pi*2
        pts.append((cx+r*(16*math.sin(t)**3)/16,
                    cy-r*(13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t))/16))
    return pts

def draw_hud(surf,player,sfont,total_levers,diff,has_map,map_big):
    BW=52
    for i in range(player.MAX_HP):
        col=RED if i<player.hp else (55,20,20)
        pygame.draw.polygon(surf,col,heart_pts(BW+22+i*34,BW//2+4,11))
        if i<player.hp: pygame.draw.polygon(surf,(255,80,80),heart_pts(BW+22+i*34,BW//2+4,5))
    lf=get_font(22,bold=True)
    lc=lf.render(f"LEVERS  {player.levers}/{total_levers}",True,WHITE)
    lcs=lf.render(f"LEVERS  {player.levers}/{total_levers}",True,(0,0,0))
    surf.blit(lcs,(SCREEN_W-BW-lc.get_width()-8,BW//2-lc.get_height()//2+2))
    surf.blit(lc, (SCREEN_W-BW-lc.get_width()-10,BW//2-lc.get_height()//2))
    hf=get_font(15,bold=True)
    hint_map="M·BigMap  " if has_map else ""
    hint_str=f"WASD·Move   Shift·Sprint   Mouse·Aim   LMB/Space·Attack   F·Flare   T·Trap   {hint_map}ESC·Pause"
    hs=hf.render(hint_str,True,(200,190,160))
    hbg=pygame.Surface((hs.get_width()+20,hs.get_height()+6),pygame.SRCALPHA)
    hbg.fill((0,0,0,160))
    surf.blit(hbg,(SCREEN_W//2-hbg.get_width()//2,SCREEN_H-BW-hs.get_height()-6))
    surf.blit(hs,(SCREEN_W//2-hs.get_width()//2,SCREEN_H-BW-hs.get_height()-3))
    bx=BW+8; by=BW+10
    sr=player.stamina/player.STAMINA_MAX
    bc=(ORANGE if player.stamina_locked==0 else (100,25,25))
    lbl="SPRINT" if player.stamina_locked==0 else "EXHAUSTED"
    _bar(surf,bx,by+16,200,12,sr,bc,lbl,(255,210,100) if player.stamina_locked==0 else (220,80,80),sfont)
    br=player.battery/player.BATTERY_MAX
    bcol=CYAN if br>0.4 else (220,180,30) if br>0.15 else (240,60,60)
    blbl="BATTERY"
    if player.battery_dead: bcol=(180,20,20); blbl="NO BATTERY — DANGER"
    _bar(surf,bx,by+52,200,12,br,bcol,blbl,(120,240,240) if br>0.4 else (240,220,80) if br>0.15 else (255,100,100),sfont)
    dc=DIFF_SETTINGS[diff]['color']; dn=DIFF_SETTINGS[diff]['name']
    df=get_font(17,bold=True)
    dt=df.render(dn,True,dc)
    dtbg=pygame.Surface((dt.get_width()+16,dt.get_height()+4),pygame.SRCALPHA)
    dtbg.fill((0,0,0,140))
    surf.blit(dtbg,(SCREEN_W//2-dtbg.get_width()//2,BW//2-dtbg.get_height()//2))
    surf.blit(dt,(SCREEN_W//2-dt.get_width()//2,BW//2-dt.get_height()//2))
    ix=BW+10; iy=SCREEN_H-BW-46
    icf=get_font(13,bold=True)
    active=[]
    if player.fx_strobe>0:     active.append(('~', (180,220,255),player.fx_strobe,   POWERUP_CFG['strobe']['duration']))
    if player.fx_overcharge>0: active.append(('OC',(255,240,80), player.fx_overcharge,POWERUP_CFG['overcharge']['duration']))
    if player.fx_adrenaline>0: active.append(('AD',(255,120,20), player.fx_adrenaline,POWERUP_CFG['adrenaline']['duration']))
    if player.fx_cloak>0:      active.append(('CL',(140,60,220), player.fx_cloak,     POWERUP_CFG['cloak']['duration']))
    if player.has_flare:       active.append(('F', (255,80,20),  1,1))
    if player.has_trap:        active.append(('T', (200,160,40), 1,1))
    for i,(icon,col,timer,maxv) in enumerate(active):
        sx=ix+i*46
        pygame.draw.circle(surf,(30,26,20),(sx+16,iy+16),18)
        pygame.draw.circle(surf,col,(sx+16,iy+16),15,2)
        it=icf.render(icon,True,col)
        surf.blit(it,(sx+16-it.get_width()//2,iy+16-it.get_height()//2))
        if maxv>1:
            ratio=timer/maxv
            pygame.draw.arc(surf,col,pygame.Rect(sx+3,iy+3,26,26),
                math.pi/2,math.pi/2+ratio*2*math.pi,2)

def _bar(surf,bx,by,bw,bh,ratio,fill_col,label,label_col,sfont):
    lf=get_font(15,bold=True)
    ls=lf.render(label,True,(0,0,0))
    surf.blit(ls,(bx+1,by-17))
    surf.blit(lf.render(label,True,label_col),(bx,by-18))
    pygame.draw.rect(surf,(20,18,14),(bx,by,bw,bh),border_radius=5)
    fw=int(bw*ratio)
    if fw>0: pygame.draw.rect(surf,fill_col,(bx,by,fw,bh),border_radius=5)
    pygame.draw.rect(surf,(100,90,70),(bx,by,bw,bh),1,border_radius=5)

# ── Screenshake ───────────────────────────────────────────────────────────────
class Screenshake:
    def __init__(self): self.trauma=0.0
    def add(self,v): self.trauma=min(1.0,self.trauma+v)
    def update(self): self.trauma=max(0.0,self.trauma-.04)
    def offset(self):
        s=self.trauma**2
        return int(random.uniform(-14,14)*s),int(random.uniform(-14,14)*s)

# ── Difficulty Select ─────────────────────────────────────────────────────────
class DifficultySelect:
    def __init__(self,fonts):
        self.font,self.big_font,self.sfont=fonts
        self.selected=DIFF_NORMAL; self.done=False; self.t=0
    def update(self): self.t+=1
    def handle_event(self,e):
        if e.type==pygame.KEYDOWN:
            if e.key in(pygame.K_LEFT,pygame.K_a):  self.selected=max(0,self.selected-1)
            if e.key in(pygame.K_RIGHT,pygame.K_d): self.selected=min(2,self.selected+1)
            if e.key==pygame.K_RETURN: self.done=True
    def draw(self,surf):
        surf.fill((4,2,6))
        title=self.big_font.render("SELECT DIFFICULTY",True,(180,20,20))
        surf.blit(title,(SCREEN_W//2-title.get_width()//2,60))
        sub=self.sfont.render("LEFT/RIGHT to choose   ENTER to confirm",True,(80,65,50))
        surf.blit(sub,(SCREEN_W//2-sub.get_width()//2,160))
        cards=[DIFF_ROOKIE,DIFF_NORMAL,DIFF_NIGHTMARE]
        cw,ch=320,380; gap=60
        total=len(cards)*(cw+gap)-gap; sx=SCREEN_W//2-total//2
        for i,d in enumerate(cards):
            ds=DIFF_SETTINGS[d]; col=ds['color']
            cx2=sx+i*(cw+gap); cy2=SCREEN_H//2-ch//2+30
            selected=d==self.selected
            bg_col=(25,20,15) if not selected else (35,28,18)
            card=pygame.Surface((cw,ch),pygame.SRCALPHA)
            pygame.draw.rect(card,(*bg_col,230),(0,0,cw,ch),border_radius=14)
            border_w=3 if selected else 1
            pulse=abs(math.sin(self.t*.04))*0.4+0.6 if selected else 1.0
            bc=(int(col[0]*pulse),int(col[1]*pulse),int(col[2]*pulse))
            pygame.draw.rect(card,(*bc,200),(0,0,cw,ch),border_w,border_radius=14)
            if selected:
                pygame.draw.rect(card,(*col,60),(0,0,6,ch),border_radius=4)
            surf.blit(card,(cx2,cy2))
            nf=get_font(32,bold=True)
            nt=nf.render(ds['name'],True,col)
            surf.blit(nt,(cx2+cw//2-nt.get_width()//2,cy2+20))
            pygame.draw.line(surf,(*col,120),(cx2+20,cy2+68),(cx2+cw-20,cy2+68),1)
            df2=get_font(17)
            for j,line in enumerate(ds['desc']):
                icon="+" if "No" not in line and "no" not in line else "-"
                ic=(80,200,80) if icon=="+" else (200,80,80)
                lt=df2.render(f"{icon} {line}",True,ic if selected else (120,110,100))
                surf.blit(lt,(cx2+18,cy2+88+j*38))
            if selected:
                af=get_font(28,bold=True)
                arr=af.render("▼ SELECTED ▼",True,col)
                surf.blit(arr,(cx2+cw//2-arr.get_width()//2,cy2+ch-45))

# ── Tutorial ──────────────────────────────────────────────────────────────────
class TutorialScreen:
    CARDS=[
        {"icon":"move",    "title":"MOVEMENT",           "lines":["WASD to move.","Hold SHIFT to sprint —","stamina bar limits it."],                    "color":AMBER},
        {"icon":"light",   "title":"FLASHLIGHT & BATTERY","lines":["Aim with the MOUSE.","Battery drains over time.","Collect cyan BATTERIES!"],          "color":CYAN},
        {"icon":"lever",   "title":"OBJECTIVE",           "lines":["Pull all levers","scattered in the building.","Then find the EXIT."],                  "color":GREEN},
        {"icon":"monster", "title":"THE DARKS",           "lines":["They navigate around walls.","In the dark they move FAST.","LMB / SPACE to fight back."],"color":RED},
        {"icon":"powerup", "title":"POWERUPS",            "lines":["Glowing orbs scattered around.","Strobe · Overcharge · Adrenaline","Cloak · MedKit · Flare(F) · Trap(T)"],"color":PURPLE},
    ]
    CARD_TIME=130; FADE=22
    def __init__(self,fonts):
        self.font,self.big_font,self.sfont=fonts; self.idx=0; self.timer=0; self.done=False
    def _alpha(self):
        t=self.timer; T=self.CARD_TIME; F=self.FADE
        if t<F: return int(255*t/F)
        if t>T-F: return int(255*(T-t)/F)
        return 255
    def update(self):
        self.timer+=1
        if self.timer>=self.CARD_TIME:
            self.timer=0; self.idx+=1
            if self.idx>=len(self.CARDS): self.done=True
    def handle_event(self,e):
        if e.type==pygame.KEYDOWN and e.key in(pygame.K_RETURN,pygame.K_SPACE):
            self.timer=0; self.idx+=1
            if self.idx>=len(self.CARDS): self.done=True
    def draw(self,surf):
        surf.fill((4,2,6))
        if self.done: return
        card=self.CARDS[self.idx]; alpha=self._alpha(); col=card["color"]
        for i in range(len(self.CARDS)):
            pygame.draw.circle(surf,col if i==self.idx else (50,45,40),
                (SCREEN_W//2-(len(self.CARDS)-1)*20+i*40,80),6)
        cw,ch=750,380; cx2,cy2=SCREEN_W//2-cw//2,SCREEN_H//2-ch//2
        panel=pygame.Surface((cw,ch),pygame.SRCALPHA)
        pygame.draw.rect(panel,(20,18,24,220),(0,0,cw,ch),border_radius=16)
        pygame.draw.rect(panel,(*col,80),(0,0,cw,ch),2,border_radius=16)
        pygame.draw.rect(panel,(*col,180),(0,0,6,ch),border_radius=4)
        panel.set_alpha(alpha); surf.blit(panel,(cx2,cy2))
        ix=cx2+30; iy=cy2+ch//2; t2=pygame.time.get_ticks()
        icon_type=card["icon"]
        if icon_type=="move":
            for kx,ky,lbl in[(ix,iy-28,"W"),(ix-22,iy+4,"A"),(ix,iy+4,"S"),(ix+22,iy+4,"D")]:
                pygame.draw.rect(surf,(50,45,55),(kx-10,ky-10,22,22),border_radius=4)
                pygame.draw.rect(surf,col,(kx-10,ky-10,22,22),1,border_radius=4)
                kt=get_font(14,bold=True).render(lbl,True,col)
                surf.blit(kt,(kx-kt.get_width()//2,ky-kt.get_height()//2))
        elif icon_type=="light":
            pygame.draw.circle(surf,col,(ix,iy),10)
            for a in[-30,-15,0,15,30]:
                ar=math.radians(a); ex=ix+int(math.cos(ar)*55); ey=iy+int(math.sin(ar)*55)
                pygame.draw.line(surf,(*col,100),(ix,iy),(ex,ey),2)
        elif icon_type=="lever":
            pygame.draw.rect(surf,(60,55,50),(ix-18,iy+10,36,14),border_radius=3)
            pygame.draw.line(surf,col,(ix,iy+10),(ix-14,iy-20),4)
            pygame.draw.circle(surf,col,(ix-14,iy-20),7)
        elif icon_type=="monster":
            pygame.draw.circle(surf,(55,10,10),(ix,iy),22)
            for i2 in range(6):
                a=i2*math.pi/3+t2*.002
                pygame.draw.line(surf,(80,0,0),(ix,iy),(int(ix+math.cos(a)*28),int(iy+math.sin(a)*28)),2)
            for ex2,ey2 in[(ix-8,iy-5),(ix+8,iy-5)]:
                pygame.draw.circle(surf,RED,(ex2,ey2),5)
                pygame.draw.circle(surf,(255,100,100),(ex2,ey2),2)
        elif icon_type=="powerup":
            orb_cols=[(180,220,255),(255,240,80),(140,60,220),(60,220,80)]
            orb_lbls=['~','!','*','+']
            for oi,(ocol,olbl) in enumerate(zip(orb_cols,orb_lbls)):
                ox2=ix-16+(oi%2)*32; oy2=iy-16+(oi//2)*32
                pulse=math.sin(t2*.004+oi*1.2)*4
                pygame.draw.circle(surf,(ocol[0]//3,ocol[1]//3,ocol[2]//3),(ox2,oy2),int(13+pulse))
                pygame.draw.circle(surf,ocol,(ox2,oy2),10)
                ot=get_font(10,bold=True).render(olbl,True,(0,0,0))
                surf.blit(ot,(ox2-ot.get_width()//2,oy2-ot.get_height()//2))
        tf=get_font(38,bold=True)
        ts=tf.render(card["title"],True,col); ts.set_alpha(alpha)
        surf.blit(ts,(cx2+140,cy2+30))
        pygame.draw.line(surf,(*col,80),(cx2+140,cy2+82),(cx2+cw-20,cy2+82),1)
        bf=get_font(19)
        for i,line in enumerate(card["lines"]):
            ls=bf.render(line,True,(200,190,170)); ls.set_alpha(alpha)
            surf.blit(ls,(cx2+140,cy2+100+i*38))
        pa=int(180*abs(math.sin((self.timer%40)/40*math.pi)))
        pt="ENTER to play!" if self.idx==len(self.CARDS)-1 else "ENTER to skip / wait..."
        ps=get_font(16).render(pt,True,col); ps.set_alpha(pa)
        surf.blit(ps,(SCREEN_W//2-ps.get_width()//2,SCREEN_H-70))

# ── States ────────────────────────────────────────────────────────────────────
S_MENU='menu'; S_SETTINGS='settings'; S_DIFFSEL='diff'; S_TUTORIAL='tut'
S_PLAY='play'; S_PAUSE='pause'; S_DEAD='dead'; S_WIN='win'; S_SCARE='scare'
S_CINEMATIC='cinematic'

# ── Intro Cinematic ───────────────────────────────────────────────────────────
class Cinematic:
    """A sequence of title-card slides that play before the game starts."""
    SLIDES = [
        dict(
            bg=(0,0,0),
            title="RIDGEWOOD RESEARCH FACILITY",
            title_col=(160,140,100),
            body=[
                "Abandoned since the incident of 1987.",
                "Power grid: offline.   Staff: missing.",
                "You were sent to retrieve the data cores.",
            ],
            body_col=(120,110,90),
            duration=210,
        ),
        dict(
            bg=(4,0,2),
            title="THE BRIEFING",
            title_col=(180,40,40),
            body=[
                "Pull every circuit lever to restore power.",
                "The backup generator will unlock the exit.",
                "Do NOT let them see you in the dark.",
            ],
            body_col=(140,80,80),
            duration=210,
        ),
        dict(
            bg=(0,0,6),
            title="WARNING",
            title_col=(220,60,60),
            body=[
                "Something still lives in those halls.",
                "They cannot be reasoned with.",
                "They hunt by light... and by sound.",
            ],
            body_col=(160,50,50),
            duration=210,
        ),
        dict(
            bg=(0,0,0),
            title="",
            title_col=(0,0,0),
            body=["Good luck.", "", "You'll need it."],
            body_col=(80,70,60),
            duration=160,
        ),
    ]
    FADE = 35   # frames for fade in / fade out

    def __init__(self, fonts):
        self.font, self.big_font, self.sfont = fonts
        self.idx   = 0
        self.timer = 0
        self.done  = False
        self._surf = pygame.Surface((SCREEN_W, SCREEN_H))

    def _alpha(self):
        t = self.timer
        T = self.SLIDES[self.idx]['duration']
        F = self.FADE
        if t < F:           return int(255 * t / F)
        if t > T - F:       return int(255 * (T - t) / F)
        return 255

    def update(self):
        self.timer += 1
        if self.timer >= self.SLIDES[self.idx]['duration']:
            self.timer = 0
            self.idx  += 1
            if self.idx >= len(self.SLIDES):
                self.done = True

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            self.timer = 0
            self.idx  += 1
            if self.idx >= len(self.SLIDES):
                self.done = True

    def draw(self, surf):
        if self.done:
            return
        sl    = self.SLIDES[self.idx]
        alpha = self._alpha()

        # background
        self._surf.fill(sl['bg'])
        surf.blit(self._surf, (0, 0))

        # decorative horizontal rule
        mid_y = SCREEN_H // 2
        rule_col = (*sl['title_col'][:3], alpha)

        # title
        if sl['title']:
            tf  = get_font(52, bold=True)
            txt = tf.render(sl['title'], True, sl['title_col'])
            txt.set_alpha(alpha)
            surf.blit(txt, (SCREEN_W // 2 - txt.get_width() // 2, mid_y - 120))

            line_surf = pygame.Surface((txt.get_width() + 80, 2), pygame.SRCALPHA)
            line_surf.fill((*sl['title_col'], alpha))
            surf.blit(line_surf, (SCREEN_W // 2 - line_surf.get_width() // 2, mid_y - 58))

        # body lines
        bf = get_font(24)
        for i, line in enumerate(sl['body']):
            bt = bf.render(line, True, sl['body_col'])
            bt.set_alpha(alpha)
            surf.blit(bt, (SCREEN_W // 2 - bt.get_width() // 2, mid_y - 20 + i * 44))

        # slide counter dots
        n = len(self.SLIDES)
        for i in range(n):
            col = sl['title_col'] if i == self.idx else (50, 45, 40)
            pygame.draw.circle(surf, col,
                (SCREEN_W // 2 - (n - 1) * 14 + i * 28, SCREEN_H - 60), 5)

        # skip hint
        hint = self.sfont.render("ENTER / SPACE to skip", True, (60, 55, 45))
        hint.set_alpha(min(alpha, 160))
        surf.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H - 36))

# ── Settings Screen ───────────────────────────────────────────────────────────
class SettingsScreen:
    def __init__(self,fonts,volume,fullscreen):
        self.font,self.big_font,self.sfont=fonts
        self.volume=volume; self.fullscreen=fullscreen
        self.done=False; self.dragging=False; self.t=0
        self.bar_w=400; self.bar_h=18

    def handle_event(self,e,screen_w,screen_h):
        bx=screen_w//2-self.bar_w//2; by=screen_h//2-20
        if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
            bar_rect=pygame.Rect(bx-8,by-8,self.bar_w+16,self.bar_h+16)
            if bar_rect.collidepoint(e.pos):
                self.dragging=True
                self.volume=max(0.0,min(1.0,(e.pos[0]-bx)/self.bar_w))
        if e.type==pygame.MOUSEBUTTONUP and e.button==1: self.dragging=False
        if e.type==pygame.MOUSEMOTION and self.dragging:
            self.volume=max(0.0,min(1.0,(e.pos[0]-bx)/self.bar_w))
        if e.type==pygame.KEYDOWN:
            if e.key in(pygame.K_ESCAPE,pygame.K_RETURN): self.done=True
            if e.key==pygame.K_LEFT:  self.volume=max(0.0,self.volume-0.05)
            if e.key==pygame.K_RIGHT: self.volume=min(1.0,self.volume+0.05)
            if e.key==pygame.K_f: self.fullscreen=not self.fullscreen

    def draw(self,surf,screen_w,screen_h):
        self.t+=1; surf.fill((4,2,6))
        title=self.big_font.render("SETTINGS",True,(180,20,20))
        surf.blit(title,(screen_w//2-title.get_width()//2,80))
        vf=get_font(26,bold=True)
        vl=vf.render("VOLUME",True,AMBER)
        surf.blit(vl,(screen_w//2-vl.get_width()//2,screen_h//2-80))
        bx=screen_w//2-self.bar_w//2; by=screen_h//2-20
        pygame.draw.rect(surf,(30,25,20),(bx,by,self.bar_w,self.bar_h),border_radius=8)
        fw=int(self.bar_w*self.volume)
        if fw>0:
            vc=(int(40+180*self.volume),int(180*self.volume),int(200*self.volume))
            pygame.draw.rect(surf,vc,(bx,by,fw,self.bar_h),border_radius=8)
        pygame.draw.rect(surf,(80,70,55),(bx,by,self.bar_w,self.bar_h),2,border_radius=8)
        kx=bx+fw; ky=by+self.bar_h//2
        pygame.draw.circle(surf,WHITE,(kx,ky),12)
        pygame.draw.circle(surf,AMBER,(kx,ky),9)
        pct=self.sfont.render(f"{int(self.volume*100)}%",True,WHITE)
        surf.blit(pct,(screen_w//2-pct.get_width()//2,by+self.bar_h+14))
        fy=screen_h//2+100
        fs_label="DISPLAY:  [ FULLSCREEN ]" if self.fullscreen else "DISPLAY:  [ WINDOWED ]"
        fs_col=GREEN if self.fullscreen else AMBER
        fs_t=vf.render(fs_label,True,fs_col)
        fsr=pygame.Rect(screen_w//2-fs_t.get_width()//2-12,fy-8,fs_t.get_width()+24,fs_t.get_height()+16)
        mx,my=pygame.mouse.get_pos()
        hov=fsr.collidepoint(mx,my)
        if hov:
            pygame.draw.rect(surf,(30,28,20),fsr,border_radius=8)
            pygame.draw.rect(surf,fs_col,fsr,2,border_radius=8)
        surf.blit(fs_t,(screen_w//2-fs_t.get_width()//2,fy))
        back=self.sfont.render("[ ENTER or ESC  to go back ]",True,(90,80,55))
        surf.blit(back,(screen_w//2-back.get_width()//2,screen_h-70))
        hint=self.sfont.render("LEFT/RIGHT arrows to adjust  ·  F to toggle fullscreen",True,(60,55,40))
        surf.blit(hint,(screen_w//2-hint.get_width()//2,screen_h-40))
        return fsr

# ── Game ──────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("SHADOWS WITHIN")
        self.screen=pygame.display.set_mode((0,0),pygame.FULLSCREEN)
        global SCREEN_W,SCREEN_H,TILE_W,TILE_H
        SCREEN_W,SCREEN_H=self.screen.get_size()
        TILE_W=SCREEN_W//COLS_MAP; TILE_H=SCREEN_H//ROWS_MAP
        _build_wall_grid()
        self.clock=pygame.time.Clock()
        self.font    =get_font(36,bold=True)
        self.big_font=get_font(72,bold=True)
        self.sfont   =get_font(18)
        # Pre-allocated surfaces
        self.bg_surf         =pygame.Surface((SCREEN_W,SCREEN_H))
        self.gs_surf         =pygame.Surface((SCREEN_W,SCREEN_H))
        self.dark_surf       =pygame.Surface((SCREEN_W,SCREEN_H))
        self.warm_surf       =pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.hurt_surf       =pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.cloak_surf      =pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.dim_surf        =pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.tablet_glow_surf=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.state=S_MENU; self.shake=Screenshake()
        self.menu_t=0; self.map_big=False
        self.cinematic=None
        self.vignette=self._bake_vignette()
        self.tutorial=None; self.diff_select=None; self.settings_screen=None
        self.diff=DIFF_NORMAL; self.is_fullscreen=True
        self.paused_from=S_MENU
        self.scare_timer=0; self.dead_timer=0; self.win_timer=0
        self.sounds=SoundManager()
        # minimap static caches
        self.mm_static=None; self.mm_static_big=None
        self.setup_level()

    def _bake_vignette(self):
        v=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        cx,cy=SCREEN_W//2,SCREEN_H//2; mr=int(math.hypot(cx,cy))
        for r in range(mr,0,-3):
            pygame.draw.circle(v,(0,0,0,int(200*(1-r/mr)**1.8)),(cx,cy),r,3)
        return v

    def _bake_static_bg(self):
        self._static_bg=pygame.Surface((SCREEN_W,SCREEN_H))
        self._static_bg.fill(DARK)
        for r,row in enumerate(LEVEL_MAP):
            for c,ch in enumerate(row):
                rect=pygame.Rect(c*TILE_W,r*TILE_H,TILE_W,TILE_H)
                if ch=='1':
                    pygame.draw.rect(self._static_bg,WALL_C,rect)
                    pygame.draw.line(self._static_bg,WALL_HL,rect.topleft,rect.topright,1)
                    pygame.draw.line(self._static_bg,WALL_HL,rect.topleft,rect.bottomleft,1)
                else:
                    pygame.draw.rect(self._static_bg,FLOOR_C,rect)

    def _bake_minimap_static(self):
        sc=MMAP_SCALE
        mw=COLS_MAP*sc; mh=ROWS_MAP*sc
        self.mm_static=pygame.Surface((mw,mh),pygame.SRCALPHA)
        self.mm_static.fill((0,0,0,160))
        for r,row in enumerate(LEVEL_MAP):
            for c,ch in enumerate(row):
                col=(70,65,80,220) if ch=='1' else (30,28,35,180)
                pygame.draw.rect(self.mm_static,col,(c*sc,r*sc,sc,sc))
        sb=MMAP_SCALE_BIG
        mwb=COLS_MAP*sb; mhb=ROWS_MAP*sb
        self.mm_static_big=pygame.Surface((mwb,mhb),pygame.SRCALPHA)
        self.mm_static_big.fill((0,0,0,200))
        for r,row in enumerate(LEVEL_MAP):
            for c,ch in enumerate(row):
                col=(70,65,80,220) if ch=='1' else (30,28,35,180)
                pygame.draw.rect(self.mm_static_big,col,(c*sb,r*sb,sb,sb))

    def _place_items(self,n,used,pool):
        p=[f for f in pool if f not in used]; random.shuffle(p)
        result=[]
        for fc,fr in p:
            if len(result)>=n: break
            result.append((fc,fr)); used.add((fc,fr))
        return result

    def setup_level(self):
        d=DIFF_SETTINGS[self.diff]
        self.TOTAL_LEVERS=d['levers']; self.has_map=d['has_map']
        self.walls=get_walls(); self.floors=safe_floor_tiles()
        mid=[f for f in self.floors if 2<=f[0]<=COLS_MAP-3 and 2<=f[1]<=ROWS_MAP-3]
        start=mid[len(mid)//5] if mid else self.floors[0]
        px,py=tile_center(*start)
        self.player=Player(px,py,self.diff)
        used={start}
        self.darks=[]
        far=[f for f in self.floors if math.hypot(tile_center(*f)[0]-px,tile_center(*f)[1]-py)>300]
        spawn_pool=far if far else [f for f in self.floors if f!=start]
        for i in range(d['num_darks']):
            if not spawn_pool: break
            if self.darks:
                spawn_pool=[f for f in spawn_pool if all(
                    math.hypot(tile_center(*f)[0]-dk.x,tile_center(*f)[1]-dk.y)>200
                    for dk in self.darks)]
            if not spawn_pool: spawn_pool=[f for f in self.floors if f!=start]
            mt=random.choice(spawn_pool)
            self.darks.append(Monster(*tile_center(*mt),self.diff))
        self.levers=[]
        zones=[
            [f for f in self.floors if f[0]<COLS_MAP//3 and f[1]<ROWS_MAP//2],
            [f for f in self.floors if COLS_MAP//3<=f[0]<2*COLS_MAP//3 and f[1]<ROWS_MAP//2],
            [f for f in self.floors if f[0]>=2*COLS_MAP//3 and f[1]<ROWS_MAP//2],
            [f for f in self.floors if f[0]<COLS_MAP//2 and f[1]>=ROWS_MAP//2],
            [f for f in self.floors if f[0]>=COLS_MAP//2 and f[1]>=ROWS_MAP//2],
        ]
        pz=self.TOTAL_LEVERS//len(zones); ez=self.TOTAL_LEVERS%len(zones)
        for zi,zone in enumerate(zones):
            for fc,fr in self._place_items(pz+(1 if zi<ez else 0),used,zone):
                self.levers.append(Lever(*tile_center(fc,fr)))
        if len(self.levers)<self.TOTAL_LEVERS:
            for fc,fr in self._place_items(self.TOTAL_LEVERS-len(self.levers),used,self.floors):
                self.levers.append(Lever(*tile_center(fc,fr)))
        self.batteries=[]
        for fc,fr in self._place_items(d['num_batteries'],used,self.floors):
            self.batteries.append(Battery(*tile_center(fc,fr)))
        ep=[f for f in self.floors if f[0]>COLS_MAP*.55 and f[1]>ROWS_MAP*.55 and f not in used]
        if not ep: ep=[f for f in self.floors if f not in used]
        self.exit_pos=tile_center(*(random.choice(ep) if ep else self.floors[-1]))
        self.powerups=[]
        for kind in POWERUP_TYPES:
            for fc,fr in self._place_items(2,used,self.floors):
                self.powerups.append(Powerup(*tile_center(fc,fr),kind))
        self.placed_traps:List[PlacedTrap]=[]
        self.active_flares:List[ActiveFlare]=[]
        self.particles:List[Particle]=[]
        self.message=""; self.message_timer=0
        self.amb_message=""; self.amb_message_timer=0
        self.ambient_timer=random.randint(300,600)
        self.fl_angle=0.0; self._battery_warned=False
        self.map_big=False
        _build_wall_grid()
        self._bake_static_bg()
        self._bake_minimap_static()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def burst(self,x,y,color,n=12):
        for _ in range(n):
            self.particles.append(Particle(x,y,color,
                vx=random.uniform(-3.5,3.5),vy=random.uniform(-3.5,1),
                life=random.randint(18,45),size=random.randint(2,5)))

    def show_msg(self,text,dur=130):
        self.message=text; self.message_timer=dur

    def draw_map(self):
        self.bg_surf.blit(self._static_bg,(0,0))
        ex,ey=self.exit_pos
        if self.player.levers>=self.TOTAL_LEVERS:
            t=pygame.time.get_ticks(); p2=int(12+math.sin(t*.005)*5)
            pygame.draw.circle(self.bg_surf,(0,80,50),(ex,ey),p2+4)
            pygame.draw.circle(self.bg_surf,GREEN,(ex,ey),p2)
            pygame.draw.circle(self.bg_surf,WHITE,(ex,ey),5)
        else:
            pygame.draw.circle(self.bg_surf,(15,40,30),(ex,ey),8)

    def draw_tablet_border(self,surf):
        T=pygame.time.get_ticks(); BW=52; RAD=28; SW,SH=SCREEN_W,SCREEN_H
        BEZEL=(18,16,22); BEZEL2=(28,25,34)
        pygame.draw.rect(surf,BEZEL,(0,0,SW,BW))
        pygame.draw.rect(surf,BEZEL,(0,SH-BW,SW,BW))
        pygame.draw.rect(surf,BEZEL,(0,0,BW,SH))
        pygame.draw.rect(surf,BEZEL,(SW-BW,0,BW,SH))
        pygame.draw.rect(surf,BEZEL2,(BW-6,BW-6,SW-BW*2+12,6))
        pygame.draw.rect(surf,BEZEL2,(BW-6,SH-BW,SW-BW*2+12,6))
        pygame.draw.rect(surf,BEZEL2,(BW-6,BW-6,6,SH-BW*2+12))
        pygame.draw.rect(surf,BEZEL2,(SW-BW,BW-6,6,SH-BW*2+12))
        glow_a=int(120+80*math.sin(T*0.0018))
        glow_col=(glow_a//3,0,glow_a//2)
        gs=self.tablet_glow_surf; gs.fill((0,0,0,0))
        for offset in range(4):
            alpha=max(0,glow_a-offset*28)
            c2=(*glow_col,alpha)
            r2=pygame.Rect(BW-2-offset,BW-2-offset,SW-BW*2+4+offset*2,SH-BW*2+4+offset*2)
            pygame.draw.rect(gs,c2,r2,2,border_radius=RAD)
        surf.blit(gs,(0,0))
        SL_COL=(255,255,255,18)
        for y in range(0,BW,8):
            pygame.draw.line(surf,SL_COL,(0,y),(SW,y),1)
            pygame.draw.line(surf,SL_COL,(0,SH-y-1),(SW,SH-y-1),1)
        CORN=(80,70,95); CORN2=(140,130,160); SIZE=28; TH=4
        corners=[(BW,BW),(SW-BW,BW),(BW,SH-BW),(SW-BW,SH-BW)]
        dirs=[(1,1),(-1,1),(1,-1),(-1,-1)]
        for (cx2,cy2),(dx,dy) in zip(corners,dirs):
            pygame.draw.line(surf,CORN2,(cx2,cy2),(cx2+dx*SIZE,cy2),TH)
            pygame.draw.line(surf,CORN2,(cx2,cy2),(cx2,cy2+dy*SIZE),TH)
            pygame.draw.circle(surf,CORN,(cx2,cy2),5)
            pygame.draw.circle(surf,CORN2,(cx2,cy2),2)
        cam_x,cam_y=SW//2,BW//2
        pygame.draw.circle(surf,(35,32,40),(cam_x,cam_y),8)
        pygame.draw.circle(surf,(50,45,60),(cam_x,cam_y),5)
        pygame.draw.circle(surf,(90,80,110),(cam_x,cam_y),2)
        for by2 in[SH//2-22,SH//2+22]:
            pygame.draw.rect(surf,(40,36,48),(0,by2-8,6,16),border_radius=3)
            pygame.draw.rect(surf,(60,55,70),(1,by2-7,4,14),border_radius=2)
        px2,py2=SW//2,SH-BW//2
        pygame.draw.rect(surf,(35,32,42),(px2-14,py2-5,28,10),border_radius=4)
        pygame.draw.rect(surf,(55,50,65),(px2-12,py2-3,24,6),border_radius=3)
        pygame.draw.rect(surf,(10,8,14),(0,0,SW,SH),3,border_radius=RAD+4)

    def _apply_display(self,fullscreen):
        global SCREEN_W,SCREEN_H,TILE_W,TILE_H
        self.is_fullscreen=fullscreen
        if fullscreen:
            self.screen=pygame.display.set_mode((0,0),pygame.FULLSCREEN)
        else:
            self.screen=pygame.display.set_mode((1280,720),pygame.RESIZABLE)
        SCREEN_W,SCREEN_H=self.screen.get_size()
        TILE_W=SCREEN_W//COLS_MAP; TILE_H=SCREEN_H//ROWS_MAP
        self.bg_surf         =pygame.Surface((SCREEN_W,SCREEN_H))
        self.gs_surf         =pygame.Surface((SCREEN_W,SCREEN_H))
        self.dark_surf       =pygame.Surface((SCREEN_W,SCREEN_H))
        self.warm_surf       =pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.hurt_surf       =pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.cloak_surf      =pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.dim_surf        =pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.tablet_glow_surf=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.vignette=self._bake_vignette()
        _FONTS.clear()
        _build_wall_grid()
        if hasattr(self,'_static_bg'): self._bake_static_bg()
        if hasattr(self,'mm_static'):  self._bake_minimap_static()

    # ── Menu ──────────────────────────────────────────────────────────────────
    def run_menu(self):
        self.menu_t+=1; self.screen.fill((4,2,6))
        flicker=1.0 if random.random()>.015 else random.uniform(.3,.7); rv=int(210*flicker)
        t1=self.big_font.render("SHADOWS",True,(rv,8,8))
        t2=self.big_font.render("WITHIN", True,(rv,rv//6,8))
        self.screen.blit(t1,(SCREEN_W//2-t1.get_width()//2,100))
        self.screen.blit(t2,(SCREEN_W//2-t2.get_width()//2,178))
        pr=int(190*abs(math.sin(self.menu_t*.035)))
        play_t=self.font.render("[ PRESS ENTER TO PLAY ]",True,(pr,int(pr*.55),0))
        self.screen.blit(play_t,(SCREEN_W//2-play_t.get_width()//2,310))
        mx,my=pygame.mouse.get_pos()
        def _btn(label,cy,hover_col=(220,60,60),base_col=(140,30,30)):
            t=self.font.render(label,True,WHITE)
            bx2=SCREEN_W//2-t.get_width()//2; r=pygame.Rect(bx2-10,cy-5,t.get_width()+20,t.get_height()+10)
            hov=r.collidepoint(mx,my)
            c=hover_col if hov else base_col
            if hov:
                pygame.draw.rect(self.screen,(30,10,10),r,border_radius=6)
                pygame.draw.rect(self.screen,c,r,2,border_radius=6)
            self.screen.blit(self.font.render(label,True,c),(bx2,cy))
            return r
        settings_r=_btn("[ SETTINGS ]",390,(200,160,20),(120,100,15))
        exit_r    =_btn("[ EXIT ]",    458,(220,60,60), (140,30,30))
        for i,line in enumerate(["Navigate the darkness · pull levers · find the exit.",
                                  "","WASD · Move   Shift · Sprint   Mouse · Aim",
                                  "LMB/Space · Attack   M · BigMap   ESC · Pause"]):
            t=self.sfont.render(line,True,(90,75,55) if line else (0,0,0))
            self.screen.blit(t,(SCREEN_W//2-t.get_width()//2,530+i*26))
        self.screen.blit(self.vignette,(0,0))
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                if exit_r.collidepoint(e.pos): pygame.quit(); sys.exit()
                if settings_r.collidepoint(e.pos):
                    self.settings_screen=SettingsScreen((self.font,self.big_font,self.sfont),self.sounds._vol,self.is_fullscreen)
                    self.paused_from=S_MENU; self.state=S_SETTINGS
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if e.key==pygame.K_RETURN:
                    self.cinematic=Cinematic((self.font,self.big_font,self.sfont))
                    self.state=S_CINEMATIC

    # ── Cinematic ─────────────────────────────────────────────────────────────
    def run_cinematic(self):
        cin = self.cinematic
        cin.update()
        cin.draw(self.screen)
        self.screen.blit(self.vignette, (0, 0))
        if cin.done:
            self.diff_select = DifficultySelect((self.font, self.big_font, self.sfont))
            self.state = S_DIFFSEL
        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            cin.handle_event(e)

    # ── Settings ──────────────────────────────────────────────────────────────
    def run_settings(self):
        ss=self.settings_screen
        fsr=ss.draw(self.screen,SCREEN_W,SCREEN_H)
        self.screen.blit(self.vignette,(0,0))
        self.sounds.set_master_volume(ss.volume)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                if fsr.collidepoint(e.pos):
                    ss.fullscreen=not ss.fullscreen
                    self._apply_display(ss.fullscreen)
            ss.handle_event(e,SCREEN_W,SCREEN_H)
        if ss.done:
            if ss.fullscreen!=self.is_fullscreen: self._apply_display(ss.fullscreen)
            self.state=self.paused_from

    # ── Difficulty Select ─────────────────────────────────────────────────────
    def run_diffsel(self):
        ds=self.diff_select; ds.update(); ds.draw(self.screen)
        self.screen.blit(self.vignette,(0,0))
        if ds.done:
            self.diff=ds.selected
            self.tutorial=TutorialScreen((self.font,self.big_font,self.sfont))
            self.state=S_TUTORIAL
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: self.state=S_MENU
            ds.handle_event(e)

    # ── Tutorial ──────────────────────────────────────────────────────────────
    def run_tutorial(self):
        tut=self.tutorial; tut.update(); tut.draw(self.screen)
        if tut.done: self.setup_level(); self.state=S_PLAY
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: self.state=S_MENU
            tut.handle_event(e)

    # ── Pause ─────────────────────────────────────────────────────────────────
    def run_pause(self):
        dim=self.dim_surf; dim.fill((0,0,0,160)); self.screen.blit(dim,(0,0))
        PW,PH=420,340; px,py=SCREEN_W//2-PW//2,SCREEN_H//2-PH//2
        panel=pygame.Surface((PW,PH),pygame.SRCALPHA)
        pygame.draw.rect(panel,(14,12,18,230),(0,0,PW,PH),border_radius=18)
        pygame.draw.rect(panel,(80,20,20,200),(0,0,PW,PH),3,border_radius=18)
        self.screen.blit(panel,(px,py))
        tf=get_font(46,bold=True)
        title=tf.render("PAUSED",True,(200,30,30))
        self.screen.blit(title,(SCREEN_W//2-title.get_width()//2,py+28))
        pygame.draw.line(self.screen,(80,20,20),(px+30,py+88),(px+PW-30,py+88),1)
        mx,my=pygame.mouse.get_pos(); bf=get_font(28,bold=True)
        def _pbtn(label,cy,danger=False):
            t=bf.render(label,True,WHITE)
            bx2=SCREEN_W//2-t.get_width()//2
            r=pygame.Rect(bx2-18,cy-8,t.get_width()+36,t.get_height()+16)
            hov=r.collidepoint(mx,my)
            hcol=(180,30,30) if danger else (60,50,80)
            bcol=(220,50,50) if danger else (100,80,140)
            tcol=(255,200,200) if danger else WHITE
            if hov:
                pygame.draw.rect(self.screen,hcol,r,border_radius=8)
                pygame.draw.rect(self.screen,bcol,r,2,border_radius=8)
            self.screen.blit(bf.render(label,True,tcol if hov else (180,170,200)),(bx2,cy))
            return r
        resume_r  =_pbtn("▶  RESUME",       py+118)
        settings_r=_pbtn("⚙  SETTINGS",     py+178)
        menu_r    =_pbtn("⌂  BACK TO MENU", py+238)
        quit_r    =_pbtn("✕  QUIT GAME",     py+298,danger=True)
        hf=get_font(14)
        ht=hf.render("ESC to resume",True,(80,70,90))
        self.screen.blit(ht,(SCREEN_W//2-ht.get_width()//2,py+PH+8))
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: self.state=S_PLAY
            if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                if resume_r.collidepoint(e.pos): self.state=S_PLAY
                elif settings_r.collidepoint(e.pos):
                    self.settings_screen=SettingsScreen((self.font,self.big_font,self.sfont),self.sounds._vol,self.is_fullscreen)
                    self.paused_from=S_PAUSE; self.state=S_SETTINGS
                elif menu_r.collidepoint(e.pos): self.state=S_MENU
                elif quit_r.collidepoint(e.pos): pygame.quit(); sys.exit()

    def _try_attack(self):
        for dk in self.darks:
            if self.player.try_attack(dk):
                dk.take_hit()
                self.burst(dk.x,dk.y,RED,14); self.shake.add(.35)
                self.show_msg("DARK HIT!" if dk.hp>0 else "DARK STAGGERED!",70)
                return

    # ── Play ──────────────────────────────────────────────────────────────────
    def run_play(self):
        keys=pygame.key.get_pressed()
        dx=int(keys[pygame.K_d]or keys[pygame.K_RIGHT])-int(keys[pygame.K_a]or keys[pygame.K_LEFT])
        dy=int(keys[pygame.K_s]or keys[pygame.K_DOWN]) -int(keys[pygame.K_w]or keys[pygame.K_UP])
        sprinting=bool(keys[pygame.K_LSHIFT]or keys[pygame.K_RSHIFT])
        mx,my=pygame.mouse.get_pos()
        self.fl_angle=math.atan2(my-self.player.y,mx-self.player.x)
        moving=self.player.move(dx,dy,self.walls,sprinting)
        self.sounds.maybe_step(moving and bool(dx or dy),sprinting)

        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: self.paused_from=S_PLAY; self.state=S_PAUSE
                if e.key==pygame.K_m and self.has_map: self.map_big=not self.map_big
                if e.key==pygame.K_SPACE: self._try_attack()
                if e.key==pygame.K_f and self.player.has_flare:
                    self.player.has_flare=False
                    fx=self.player.x+math.cos(self.fl_angle)*120
                    fy=self.player.y+math.sin(self.fl_angle)*120
                    tc=world_to_tile(fx,fy)
                    if not is_floor(*tc): fx,fy=self.player.x,self.player.y
                    self.active_flares.append(ActiveFlare(fx,fy))
                    self.show_msg("FLARE THROWN!",80)
                if e.key==pygame.K_t and self.player.has_trap:
                    self.player.has_trap=False
                    self.placed_traps.append(PlacedTrap(int(self.player.x),int(self.player.y)))
                    self.show_msg("TRAP SET!",80)
            if e.type==pygame.MOUSEBUTTONDOWN and e.button==1: self._try_attack()

        prev_dead=self.player.battery_dead
        self.player.drain_battery()
        if self.player.battery_dead and not prev_dead:
            self.show_msg("BATTERY DEAD — IT CAN SMELL YOU NOW!",260)
            self.shake.add(.6); self.sounds.play('growl',1.5)
        ratio=self.player.battery/self.player.BATTERY_MAX
        if ratio<0.15 and not self._battery_warned and not self.player.battery_dead:
            self._battery_warned=True; self.show_msg("BATTERY LOW — find a battery!",200)
        if ratio>0.2: self._battery_warned=False

        self.player.update()
        p=self.player
        if p.fx_strobe>0:    p.fx_strobe-=1
        if p.fx_overcharge>0:p.fx_overcharge-=1
        if p.fx_adrenaline>0:p.fx_adrenaline-=1
        if p.fx_cloak>0:     p.fx_cloak-=1

        for pu in self.powerups:
            pu.update()
            if pu.check_collect(self.player):
                k=pu.kind; cfg=POWERUP_CFG[k]
                self.burst(pu.x,pu.y,cfg['color'],18); self.shake.add(.15)
                self.sounds.play('battery',0.4)
                if k=='strobe':
                    p.fx_strobe=cfg['duration']; self.show_msg("STROBE ACTIVE!",160)
                elif k=='overcharge':
                    p.fx_overcharge=cfg['duration']; self.show_msg("FLASHLIGHT OVERCHARGED!",160)
                elif k=='adrenaline':
                    p.fx_adrenaline=cfg['duration']; p.stamina=p.STAMINA_MAX
                    self.show_msg("ADRENALINE! Unlimited sprint!",160)
                elif k=='cloak':
                    p.fx_cloak=cfg['duration']; self.show_msg("SHADOW CLOAK active!",160)
                elif k=='flare':
                    p.has_flare=True; self.show_msg("FLARE — press F to throw!",160)
                elif k=='medkit':
                    if p.hp<p.MAX_HP: p.hp+=1
                    self.show_msg("MED KIT — Health restored!",140)
                elif k=='trap':
                    p.has_trap=True; self.show_msg("TRAP — press T to place!",160)

        for tr in self.placed_traps:
            tr.update(self.darks)
            if tr.triggered and tr.stun_timer==5*60-1:
                self.show_msg("DARK TRAPPED!",120); self.shake.add(.2)
        self.placed_traps=[tr for tr in self.placed_traps if tr.alive()]

        for fl2 in self.active_flares: fl2.update()
        self.active_flares=[fl2 for fl2 in self.active_flares if fl2.alive()]

        bat_r=p.battery/p.BATTERY_MAX
        fl_len=int(80+240*bat_r); fl_fov=int(25+55*bat_r); fl_alpha=int(120+110*bat_r)
        if p.fx_overcharge>0:
            fl_len=int(fl_len*2.0); fl_fov=min(140,int(fl_fov*1.7)); fl_alpha=min(255,fl_alpha+60)
        strobe_on=p.fx_strobe>0 and (pygame.time.get_ticks()//80)%2==0
        if strobe_on: fl_len=int(fl_len*1.3); fl_fov=min(130,fl_fov+20)
        if p.battery_dead: fl_poly=[]
        else: fl_poly=cast_flashlight(p.pos,self.fl_angle,fl_fov,self.walls,fl_len,48)

        if p.fx_adrenaline>0: p.stamina=p.STAMINA_MAX; p.stamina_locked=0

        cloaked=p.fx_cloak>0
        for dk in self.darks:
            if cloaked: in_fl=False; bd_eff=False
            else:
                in_fl=(point_in_poly(dk.x,dk.y,fl_poly) if fl_poly else False)
                bd_eff=p.battery_dead
            if strobe_on and in_fl and dk.stun_timer<=0: dk.stun_timer=90
            if self.active_flares and dk.mode!='chase':
                nearest=min(self.active_flares,key=lambda f:math.hypot(f.x-dk.x,f.y-dk.y))
                if math.hypot(nearest.x-dk.x,nearest.y-dk.y)<ActiveFlare.ATTRACT_R:
                    dk.patrol_target=(nearest.x,nearest.y); dk.patrol_timer=60
            dk.update(p,self.walls,self.floors,in_fl,bd_eff,cloaked)

        if any(dk.mode=='chase' for dk in self.darks):
            self.sounds.play_growl()
            self.sounds.set_drone_volume(0.35+0.2*math.sin(pygame.time.get_ticks()*.003))

        for lv in self.levers:
            lv.update()
            if lv.check_collect(p):
                p.levers+=1; self.burst(lv.x,lv.y,AMBER,16); self.shake.add(.12)
                self.sounds.play('lever')
                rem=self.TOTAL_LEVERS-p.levers
                self.show_msg(f"LEVER PULLED! {rem} remaining." if rem else "ALL LEVERS PULLED! FIND THE EXIT!",
                              130 if rem else 200)

        for b in self.batteries:
            b.update()
            if b.check_collect(p):
                p.recharge(Battery.RECHARGE); p.battery_dead=False; self._battery_warned=False
                self.burst(b.x,b.y,CYAN,14); self.shake.add(.1)
                self.sounds.play('battery'); self.show_msg("BATTERY RECHARGED!",110)

        ex,ey=self.exit_pos
        if p.levers>=self.TOTAL_LEVERS and math.hypot(ex-p.x,ey-p.y)<26:
            self.win_timer=0; self.state=S_WIN; self.sounds.play('win')
        if p.hp<=0:
            self.scare_timer=0; self.state=S_SCARE; self.shake.add(1.0); self.sounds.play('die')

        # Ambient messages
        self.ambient_timer-=1
        if self.ambient_timer<=0:
            self.ambient_timer=random.randint(280,560)
            amb_events=[
                ("scrape",     "...something scrapes against the wall nearby."),
                ("scrape",     "...the pipes are groaning."),
                ("ghost_step", "...footsteps. Behind you."),
                ("ghost_step", "...tap. tap. tap. The sound stops."),
                ("door_slam",  "...a door slams somewhere in the building."),
                ("door_slam",  "...a heavy crash echoes through the halls."),
            ]
            snd_name,msg=random.choice(amb_events)
            self.sounds.play_ambient(snd_name)
            self.amb_message=msg; self.amb_message_timer=220

        for pt in self.particles: pt.update()
        self.particles=[pt for pt in self.particles if pt.alive()]
        if p.hurt_timer==79:
            self.burst(p.x,p.y,(255,40,40),14); self.shake.add(.55); self.sounds.play('hurt')
        self.shake.update()

        # ── Render ────────────────────────────────────────────────────────────
        self.draw_map()
        ox,oy=self.shake.offset()
        gs=self.gs_surf; gs.blit(self.bg_surf,(0,0))
        for lv in self.levers: lv.draw(gs)
        for b  in self.batteries: b.draw(gs)
        for pu in self.powerups:  pu.draw(gs)
        for tr in self.placed_traps: tr.draw(gs)
        for fl2 in self.active_flares: fl2.draw(gs)
        for dk in self.darks:
            in_fl2=(point_in_poly(dk.x,dk.y,fl_poly) if fl_poly else False)
            dk.draw(gs,in_fl2)
        p.draw(gs,self.fl_angle)
        for pt in self.particles: pt.draw(gs)

        dark_surf=self.dark_surf; dark_surf.fill((0,0,0))
        amb_col=(18,8,8) if p.battery_dead else (14,10,4)
        pygame.draw.circle(dark_surf,amb_col,(int(p.x),int(p.y)),45)
        if fl_poly and len(fl_poly)>=3:
            pygame.draw.polygon(dark_surf,(255,0,255),fl_poly)
            dark_surf.set_colorkey((255,0,255))
            warm=self.warm_surf; warm.fill((0,0,0,0))
            pygame.draw.polygon(warm,(255,200,120,max(0,fl_alpha-180)),fl_poly)
            gs.blit(warm,(0,0))
        else:
            dark_surf.set_colorkey(None)
        gs.blit(dark_surf,(0,0))

        if p.hurt_timer>0:
            hs=self.hurt_surf; hs.fill((190,0,0,min(int(110*p.hurt_timer/80),110)))
            gs.blit(hs,(0,0))
        if p.fx_cloak>0:
            fade=min(1.0,p.fx_cloak/30)
            cs=self.cloak_surf; cs.fill((60,0,100,int(40*fade)))
            gs.blit(cs,(0,0))

        gs.blit(self.vignette,(0,0))
        self.screen.blit(gs,(ox,oy))
        draw_hud(self.screen,p,self.sfont,self.TOTAL_LEVERS,self.diff,self.has_map,self.map_big)

        if self.has_map and not self.map_big:
            draw_minimap(self.screen,p,self.levers,self.batteries,self.exit_pos,
                         self.darks,self.TOTAL_LEVERS,self.sfont,big=False,
                         mm_static=self.mm_static,mm_static_big=self.mm_static_big)
        if self.has_map and self.map_big:
            dim=self.dim_surf; dim.fill((0,0,0,140)); self.screen.blit(dim,(0,0))
            draw_minimap(self.screen,p,self.levers,self.batteries,self.exit_pos,
                         self.darks,self.TOTAL_LEVERS,self.sfont,big=True,
                         mm_static=self.mm_static,mm_static_big=self.mm_static_big)

        self.draw_tablet_border(self.screen)

        if p.battery_dead and (pygame.time.get_ticks()//600)%2==0:
            bd=self.sfont.render("NO LIGHT",True,DARK_RED)
            self.screen.blit(bd,(SCREEN_W//2-bd.get_width()//2,72))
        if self.message_timer>0:
            self.message_timer-=1
            a=min(255,self.message_timer*5)
            col=(min(255,int(AMBER[0]*a/255)),min(255,int(AMBER[1]*a/255)),0)
            mt=self.sfont.render(self.message,True,col)
            self.screen.blit(mt,(SCREEN_W//2-mt.get_width()//2,SCREEN_H//2-70))
        if self.amb_message_timer>0:
            self.amb_message_timer-=1
            a=min(255,self.amb_message_timer*4)
            af=get_font(17); amb_col=(140,160,180)
            at=af.render(self.amb_message,True,amb_col); at.set_alpha(a)
            self.screen.blit(at,(SCREEN_W//2-at.get_width()//2,SCREEN_H-130))

    # ── Jumpscare ─────────────────────────────────────────────────────────────
    def run_scare(self):
        self.scare_timer+=1; T=self.scare_timer; SCARE_FRAMES=55
        if T<=18:
            intensity=1.0-(T/18)*0.5; r=int(220*intensity); self.screen.fill((r,0,0))
            scale=0.3+T/18*2.8; cx,cy=SCREEN_W//2,SCREEN_H//2; base=int(80*scale)
            pygame.draw.circle(self.screen,(30,5,5),(cx,cy),base+int(base*0.15))
            pygame.draw.circle(self.screen,(55,10,10),(cx,cy),base)
            for i in range(12):
                a=i*math.pi/6+T*0.04
                slen=base+int(20*scale*math.sin(T*0.3+i))
                pygame.draw.line(self.screen,(80,0,0),(cx,cy),
                    (int(cx+math.cos(a)*slen),int(cy+math.sin(a)*slen)),max(1,int(3*scale)))
            for ex2,ey2 in[(cx-int(22*scale),cy-int(8*scale)),(cx+int(22*scale),cy-int(8*scale))]:
                pygame.draw.circle(self.screen,(180,0,0),(ex2,ey2),int(14*scale))
                pygame.draw.circle(self.screen,(255,60,60),(ex2,ey2),int(7*scale))
                pygame.draw.circle(self.screen,(255,200,200),(ex2,ey2),int(3*scale))
            mouth_w=int(40*scale); mouth_h=int(18*scale)
            pygame.draw.ellipse(self.screen,(10,0,0),(cx-mouth_w//2,cy+int(20*scale),mouth_w,mouth_h))
            self.shake.trauma=min(1.0,1.0-T/18*0.4)
        elif T<=38:
            fade=1.0-(T-18)/20; r=int(220*fade*0.3); self.screen.fill((r,0,0))
            cx,cy=SCREEN_W//2,SCREEN_H//2; base=int(80*3.1)
            pygame.draw.circle(self.screen,(int(30*fade),0,0),(cx,cy),base+int(base*0.15))
            pygame.draw.circle(self.screen,(int(55*fade),0,0),(cx,cy),base)
            for i in range(12):
                a=i*math.pi/6; c2=int(80*fade)
                pygame.draw.line(self.screen,(c2,0,0),(cx,cy),
                    (int(cx+math.cos(a)*(base+20)),int(cy+math.sin(a)*(base+20))),3)
            for ex2,ey2 in[(cx-int(22*3.1),cy-int(8*3.1)),(cx+int(22*3.1),cy-int(8*3.1))]:
                pygame.draw.circle(self.screen,(int(180*fade),0,0),(ex2,ey2),int(14*3.1))
                pygame.draw.circle(self.screen,(int(255*fade),int(60*fade),0),(ex2,ey2),int(7*3.1))
        else:
            self.screen.fill((0,0,0))
        self.shake.update()
        ox,oy=self.shake.offset()
        if ox or oy:
            tmp=self.screen.copy(); self.screen.fill((0,0,0)); self.screen.blit(tmp,(ox,oy))
        if T>=SCARE_FRAMES:
            self.dead_timer=0; self.state=S_DEAD
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()

    # ── Dead ──────────────────────────────────────────────────────────────────
    def run_dead(self):
        self.dead_timer+=1; t=self.dead_timer
        alpha=min(255,int(t*3))
        bg=pygame.Surface((SCREEN_W,SCREEN_H)); bg.fill((5,0,0)); bg.set_alpha(alpha)
        self.screen.fill((0,0,0)); self.screen.blit(bg,(0,0))
        if alpha>60:
            tf=get_font(72,bold=True); title=tf.render("YOU DIED",True,BLOOD)
            title.set_alpha(min(255,int((alpha-60)*3)))
            self.screen.blit(title,(SCREEN_W//2-title.get_width()//2,SCREEN_H//2-90))
        if alpha>120:
            sf=get_font(28); sub=sf.render("The darkness consumed you.",True,(110,35,35))
            sub.set_alpha(min(255,int((alpha-120)*3)))
            self.screen.blit(sub,(SCREEN_W//2-sub.get_width()//2,SCREEN_H//2+10))
        if alpha>=200:
            bf=get_font(22,bold=True)
            mx,my=pygame.mouse.get_pos()
            def _dbtn(label,cy,col):
                t2=bf.render(label,True,WHITE)
                bx2=SCREEN_W//2-t2.get_width()//2
                r=pygame.Rect(bx2-14,cy-8,t2.get_width()+28,t2.get_height()+16)
                hov=r.collidepoint(mx,my)
                if hov:
                    pygame.draw.rect(self.screen,(40,10,10),r,border_radius=6)
                    pygame.draw.rect(self.screen,col,r,2,border_radius=6)
                self.screen.blit(bf.render(label,True,col if hov else (150,50,50)),(bx2,cy))
                return r
            again_r=_dbtn("▶  Play Again", SCREEN_H//2+80, (220,60,60))
            menu_r =_dbtn("⌂  Main Menu",  SCREEN_H//2+130,(160,40,40))
            for e in pygame.event.get():
                if e.type==pygame.QUIT: pygame.quit(); sys.exit()
                if e.type==pygame.KEYDOWN and e.key==pygame.K_RETURN:
                    self.setup_level(); self.state=S_PLAY
                if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                    if again_r.collidepoint(e.pos): self.setup_level(); self.state=S_PLAY
                    elif menu_r.collidepoint(e.pos): self.state=S_MENU
            return
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()

    # ── Win ───────────────────────────────────────────────────────────────────
    def run_win(self):
        self.win_timer+=1; t=self.win_timer
        alpha=min(255,int(t*3))
        bg=pygame.Surface((SCREEN_W,SCREEN_H)); bg.fill((2,8,4)); bg.set_alpha(alpha)
        self.screen.fill((0,0,0)); self.screen.blit(bg,(0,0))
        if alpha>60:
            tf=get_font(72,bold=True); title=tf.render("ESCAPED!",True,GREEN)
            title.set_alpha(min(255,int((alpha-60)*3)))
            self.screen.blit(title,(SCREEN_W//2-title.get_width()//2,SCREEN_H//2-90))
        if alpha>120:
            sf=get_font(28); sub=sf.render("The nightmare ends... for now.",True,TEAL)
            sub.set_alpha(min(255,int((alpha-120)*3)))
            self.screen.blit(sub,(SCREEN_W//2-sub.get_width()//2,SCREEN_H//2+10))
        if alpha>=200:
            bf=get_font(22,bold=True)
            mx,my=pygame.mouse.get_pos()
            def _wbtn(label,cy,col):
                t2=bf.render(label,True,WHITE)
                bx2=SCREEN_W//2-t2.get_width()//2
                r=pygame.Rect(bx2-14,cy-8,t2.get_width()+28,t2.get_height()+16)
                hov=r.collidepoint(mx,my)
                if hov:
                    pygame.draw.rect(self.screen,(10,40,20),r,border_radius=6)
                    pygame.draw.rect(self.screen,col,r,2,border_radius=6)
                self.screen.blit(bf.render(label,True,col if hov else (50,150,70)),(bx2,cy))
                return r
            again_r=_wbtn("▶  Play Again",SCREEN_H//2+80, (60,200,80))
            menu_r =_wbtn("⌂  Main Menu", SCREEN_H//2+130,(40,140,60))
            for e in pygame.event.get():
                if e.type==pygame.QUIT: pygame.quit(); sys.exit()
                if e.type==pygame.KEYDOWN and e.key==pygame.K_RETURN:
                    self.tutorial=TutorialScreen((self.font,self.big_font,self.sfont))
                    self.state=S_TUTORIAL
                if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                    if again_r.collidepoint(e.pos):
                        self.tutorial=TutorialScreen((self.font,self.big_font,self.sfont))
                        self.state=S_TUTORIAL
                    elif menu_r.collidepoint(e.pos): self.state=S_MENU
            return
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()

    # ── Loop ──────────────────────────────────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(FPS)
            if   self.state==S_MENU:       self.run_menu()
            elif self.state==S_CINEMATIC:  self.run_cinematic()
            elif self.state==S_SETTINGS:   self.run_settings()
            elif self.state==S_DIFFSEL:  self.run_diffsel()
            elif self.state==S_TUTORIAL: self.run_tutorial()
            elif self.state==S_PLAY:     self.run_play()
            elif self.state==S_PAUSE:    self.run_pause()
            elif self.state==S_SCARE:    self.run_scare()
            elif self.state==S_DEAD:     self.run_dead()
            elif self.state==S_WIN:      self.run_win()
            pygame.display.flip()

if __name__=="__main__":
    Game().run()