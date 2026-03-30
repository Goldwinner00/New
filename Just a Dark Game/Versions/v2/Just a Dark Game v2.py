"""
SHADOWS WITHIN  —  Pygame Survival Horror
WASD=Move  Shift=Sprint  Mouse=Aim  LMB/Space=Attack  M=BigMap  ESC=Quit
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
        name="ROOKIE",
        color=(60,200,80),
        levers=10,
        monster_chase=1.8, monster_patrol=1.2, monster_dark=3.5,
        battery_max=2400, battery_drain=1,
        stamina_max=420, stamina_drain=1, stamina_regen=1.0, stamina_lock=60,
        num_batteries=10, has_map=True,
        desc=["Slower monster","10 levers","More stamina","More batteries"],
    ),
    DIFF_NORMAL: dict(
        name="NORMAL",
        color=(220,180,30),
        levers=15,
        monster_chase=2.8, monster_patrol=1.8, monster_dark=5.5,
        battery_max=1500, battery_drain=1,
        stamina_max=300, stamina_drain=2, stamina_regen=0.8, stamina_lock=90,
        num_batteries=10, has_map=True,
        desc=["Standard speed","15 levers","Normal stamina","Standard batteries"],
    ),
    DIFF_NIGHTMARE: dict(
        name="NIGHTMARE",
        color=(220,30,30),
        levers=20,
        monster_chase=4.2, monster_patrol=2.5, monster_dark=7.0,
        battery_max=900, battery_drain=1,
        stamina_max=380, stamina_drain=2, stamina_regen=1.0, stamina_lock=70,
        num_batteries=8, has_map=False,
        desc=["Fast monster","20 levers","NO MAP","Shorter battery"],
    ),
}

# ── Map ───────────────────────────────────────────────────────────────────────
LEVEL_MAP = [
    "111111111111111111111111111111111",
    "100000000010000000001000000000001",
    "101111010010111101001011110101101",
    "100001010000100001001000000101001",
    "111101011110100001111011110101111",
    "100001000010100000000010000000001",
    "101111011010111111011010111111001",
    "101000011000000001011010000001001",
    "101011111011111001011011111001001",
    "101010000000001001000000001001001",
    "101010111000001001011111001001111",
    "101010100000001001010000001000001",
    "101010100011111111010111111011101",
    "100010100000000000010100000010001",
    "111110111111101111110101111110111",
    "100000000010000000000001000000001",
    "101111111010111111111001011111101",
    "100000001010000000001001000000001",
    "111111111111111111111111111111111",
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

# ── Sound manager — pure Python, zero external dependencies ──────────────────
class SoundManager:
    SR = 44100   # sample rate

    def __init__(self):
        try:
            pygame.mixer.init(frequency=self.SR, size=-16, channels=2, buffer=1024)
            self._ok = True
        except Exception:
            self._ok = False
            return
        self._sounds = {}
        self._ch_drone  = pygame.mixer.Channel(0)
        self._ch_growl  = pygame.mixer.Channel(1)
        self._ch_sfx    = pygame.mixer.Channel(2)
        self._ch_step   = pygame.mixer.Channel(3)
        self._step_timer = 0
        self._build_all()

    # ── core synth: pure Python array, no numpy ───────────────────────────────
    def _make(self, dur, vol, *partials, noise=0.0, atk=0.02, rel=0.15):
        """
        partials: list of (freq, wave, amp) tuples.
        wave: 'sin', 'sqr', 'saw'
        Returns a pygame.mixer.Sound.
        """
        import array as arr
        n   = int(self.SR * dur)
        atk_n = max(1, int(atk * self.SR))
        rel_n = max(1, int(rel * self.SR))
        buf = arr.array('h', bytes(n * 4))   # stereo int16 → 4 bytes/frame
        for i in range(n):
            t = i / self.SR
            # envelope
            if i < atk_n:           env = i / atk_n
            elif i > n - rel_n:     env = (n - i) / rel_n
            else:                   env = 1.0
            s = 0.0
            for freq, wave, amp in partials:
                phase = freq * t
                if wave == 'sin':
                    s += amp * math.sin(2 * math.pi * phase)
                elif wave == 'sqr':
                    s += amp * (1.0 if math.sin(2 * math.pi * phase) > 0 else -1.0)
                elif wave == 'saw':
                    s += amp * 2.0 * (phase - math.floor(phase + 0.5))
            if noise > 0:
                s += noise * random.uniform(-1.0, 1.0)
            sample = int(max(-1.0, min(1.0, s)) * env * vol * 32767)
            buf[i * 2]     = sample   # left
            buf[i * 2 + 1] = sample   # right
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _build_all(self):
        try:
            # footstep — short noise burst
            self._sounds['step'] = self._make(
                0.07, 0.18, noise=0.9, atk=0.005, rel=0.06)
            # lever click — square blip + low tone
            self._sounds['lever'] = self._make(
                0.22, 0.32,
                (180, 'sqr', 0.6), (90, 'sin', 0.4),
                atk=0.005, rel=0.18)
            # battery chime — bright sine chord
            self._sounds['battery'] = self._make(
                0.30, 0.35,
                (880, 'sin', 0.5), (1108, 'sin', 0.3), (660, 'sin', 0.2),
                atk=0.01, rel=0.22)
            # hurt — noise thud
            self._sounds['hurt'] = self._make(
                0.35, 0.50,
                (100, 'sin', 0.4), (60, 'saw', 0.3),
                noise=0.5, atk=0.005, rel=0.28)
            # growl — low saw rumble
            self._sounds['growl'] = self._make(
                0.55, 0.30,
                (55, 'saw', 0.5), (82, 'saw', 0.3), (41, 'sin', 0.2),
                noise=0.1, atk=0.05, rel=0.35)
            # win — rising major chord
            self._sounds['win'] = self._make(
                0.60, 0.38,
                (523, 'sin', 0.5), (659, 'sin', 0.35), (784, 'sin', 0.25),
                atk=0.02, rel=0.40)
            # die — descending saw
            self._sounds['die'] = self._make(
                0.75, 0.42,
                (220, 'saw', 0.5), (110, 'saw', 0.3), (165, 'sin', 0.2),
                noise=0.15, atk=0.01, rel=0.55)
            # drone loop — layered low sines (4 s)
            self._sounds['drone'] = self._make(
                4.0, 0.20,
                (55, 'sin', 0.45), (82, 'sin', 0.30),
                (110, 'sin', 0.15), (27, 'sin', 0.10),
                noise=0.03, atk=0.5, rel=0.5)
            # start drone loop
            self._sounds['drone'].set_volume(0.18)
            self._ch_drone.play(self._sounds['drone'], loops=-1)
        except Exception as e:
            self._ok = False

    # ── public API ────────────────────────────────────────────────────────────
    def play(self, name, vol=None):
        if not self._ok: return
        snd = self._sounds.get(name)
        if not snd: return
        if vol is not None: snd.set_volume(max(0.0, min(1.0, vol)))
        self._ch_sfx.play(snd)

    def play_growl(self):
        if not self._ok: return
        if not self._ch_growl.get_busy():
            self._sounds['growl'].set_volume(0.28)
            self._ch_growl.play(self._sounds['growl'])

    def maybe_step(self, moving):
        if not self._ok or not moving: return
        self._step_timer -= 1
        if self._step_timer <= 0:
            self._step_timer = 20
            self._ch_step.play(self._sounds['step'])

    def set_drone_volume(self, vol):
        if not self._ok: return
        self._ch_drone.set_volume(max(0.0, min(1.0, vol)))

# ── Flashlight ────────────────────────────────────────────────────────────────
def cast_flashlight(pos, angle, fov_deg, walls, length=300, rays=64):
    half=math.radians(fov_deg/2); pts=[pos]
    for i in range(rays+1):
        a=angle-half+(2*half*i/rays)
        cdx,cdy=math.cos(a),math.sin(a); best=length
        for w in walls:
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
        self.STAMINA_MAX=d['stamina_max']
        self.STAMINA_DRAIN=d['stamina_drain']
        self.STAMINA_REGEN=d['stamina_regen']
        self.STAMINA_LOCK=d['stamina_lock']
        self.BATTERY_MAX=d['battery_max']
        self.BATTERY_DRAIN=d['battery_drain']
        self.stamina=float(self.STAMINA_MAX); self.stamina_locked=0
        self.is_sprinting=False
        self.battery=float(self.BATTERY_MAX); self.battery_dead=False

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
        self.x+=dx
        for w in walls:
            if self.rect.colliderect(w):
                self.x=(w.left-self.RADIUS) if dx>0 else (w.right+self.RADIUS)
        self.y+=dy
        for w in walls:
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
        self.path=[]; self.path_timer=0
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
        self.x+=nx
        for w in walls:
            if self.rect.colliderect(w):
                self.x=w.left-self.RADIUS if nx>0 else w.right+self.RADIUS
        self.y+=ny
        for w in walls:
            if self.rect.colliderect(w):
                self.y=w.top-self.RADIUS if ny>0 else w.bottom+self.RADIUS

    def update(self,player,walls,floors,in_fl,battery_dead):
        if self.attack_timer>0: self.attack_timer-=1
        if self.hurt_timer>0:   self.hurt_timer-=1
        self.path_timer=max(0,self.path_timer-1)
        dist_p=math.hypot(player.x-self.x,player.y-self.y)
        can_detect=(dist_p<self.HEAR_RANGE or in_fl or battery_dead or self.mode=='chase')
        if can_detect:
            self.mode='chase'; self.last_known=(player.x,player.y); self.search_timer=400
        spd=self.DARK_SPEED if battery_dead else self.CHASE_SPEED
        if self.mode=='chase':
            tx,ty=player.x,player.y
            if not can_detect:
                self.search_timer-=1
                if self.search_timer<=0:
                    self.mode='search'; self.search_timer=random.randint(300,500)
            if self.path_timer==0: self._refresh_path(tx,ty)
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
        glow=pygame.Surface((gr*2+4,gr*2+4),pygame.SRCALPHA)
        pygame.draw.circle(glow,(255,200,40,50),(gr+2,gr+2),gr)
        surf.blit(glow,(cx-gr-2,cy-gr-2))
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
        glow=pygame.Surface((gr*2+4,gr*2+4),pygame.SRCALPHA)
        pygame.draw.circle(glow,(40,220,220,45),(gr+2,gr+2),gr); surf.blit(glow,(cx-gr-2,cy-gr-2))
        pygame.draw.rect(surf,(20,80,90),(cx-7,cy-5,14,10),border_radius=2)
        pygame.draw.rect(surf,CYAN,(cx-6,cy-4,12,8),border_radius=1)
        pygame.draw.rect(surf,CYAN,(cx+7,cy-2,3,4),border_radius=1)
        f=pygame.font.SysFont("courier",9,bold=True)
        t=f.render("+",True,WHITE); surf.blit(t,(cx-t.get_width()//2,cy-t.get_height()//2))
    def check_collect(self,player):
        if self.collected: return False
        if math.hypot(self.x-player.x,self.y-player.y)<22:
            self.collected=True; return True
        return False

# ── Minimap ───────────────────────────────────────────────────────────────────
MMAP_SCALE=6
MMAP_W=COLS_MAP*MMAP_SCALE; MMAP_H=ROWS_MAP*MMAP_SCALE
MMAP_X=SCREEN_W-MMAP_W-12;  MMAP_Y=40
MMAP_SCALE_BIG=14
MMAP_W_BIG=COLS_MAP*MMAP_SCALE_BIG; MMAP_H_BIG=ROWS_MAP*MMAP_SCALE_BIG

def draw_minimap(surf,player,levers,batteries,exit_pos,monster,total_levers,sfont,big=False):
    sc  = MMAP_SCALE_BIG if big else MMAP_SCALE
    mw  = COLS_MAP*sc; mh = ROWS_MAP*sc
    mx0 = SCREEN_W//2-mw//2 if big else MMAP_X
    my0 = SCREEN_H//2-mh//2 if big else MMAP_Y

    mm=pygame.Surface((mw,mh),pygame.SRCALPHA)
    mm.fill((0,0,0,200 if big else 160))
    for r,row in enumerate(LEVEL_MAP):
        for c,ch in enumerate(row):
            col=(70,65,80,220) if ch=='1' else (30,28,35,180)
            pygame.draw.rect(mm,col,(c*sc,r*sc,sc,sc))

    if player.levers>=total_levers:
        ex_mm=int(exit_pos[0]/TILE_W*sc); ey_mm=int(exit_pos[1]/TILE_H*sc)
        pygame.draw.circle(mm,GREEN,(ex_mm,ey_mm),max(4,sc//3))

    tick=pygame.time.get_ticks()
    for lv in levers:
        if not lv.collected:
            blink=(tick//500)%2==0
            lx=int(lv.x/TILE_W*sc); ly=int(lv.y/TILE_H*sc)
            pygame.draw.circle(mm,AMBER if blink else (180,120,20),(lx,ly),max(3,sc//4))
    for b in batteries:
        if not b.collected:
            bx2=int(b.x/TILE_W*sc); by2=int(b.y/TILE_H*sc)
            pygame.draw.circle(mm,CYAN,(bx2,by2),max(3,sc//4))

    mx_mm=int(monster.x/TILE_W*sc); my_mm=int(monster.y/TILE_H*sc)
    ping=(tick%1200)/1200.0; ring_r=int(2+ping*12); ring_a=int(255*(1-ping))
    if ring_a>10:
        rs=pygame.Surface((mw,mh),pygame.SRCALPHA)
        pygame.draw.circle(rs,(200,0,0,ring_a),(mx_mm,my_mm),ring_r,1); mm.blit(rs,(0,0))
    pygame.draw.circle(mm,RED if monster.mode=='chase' else (130,25,25),(mx_mm,my_mm),max(3,sc//3))

    px_mm=int(player.x/TILE_W*sc); py_mm=int(player.y/TILE_H*sc)
    pygame.draw.circle(mm,AMBER,(px_mm,py_mm),max(3,sc//3))

    surf.blit(mm,(mx0,my0))
    pygame.draw.rect(surf,(80,70,60),(mx0-1,my0-1,mw+2,mh+2),1)
    if big:
        lbl=sfont.render("MAP  [M to close]",True,(120,110,80))
        surf.blit(lbl,(mx0,my0-22))
        # semi-transparent backdrop
        bg=pygame.Surface((mw+20,mh+40),pygame.SRCALPHA)
        bg.fill((0,0,0,160)); surf.blit(bg,(mx0-10,my0-30))
        surf.blit(mm,(mx0,my0))
        pygame.draw.rect(surf,(80,70,60),(mx0-1,my0-1,mw+2,mh+2),2)
        surf.blit(lbl,(mx0,my0-22))
    else:
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
    for i in range(player.MAX_HP):
        pygame.draw.polygon(surf,RED if i<player.hp else (50,20,20),heart_pts(22+i*30,22,10))
    lc=sfont.render(f"LEVERS  {player.levers}/{total_levers}",True,AMBER)
    surf.blit(lc,(SCREEN_W-220,10))
    hint_map="M·BigMap" if has_map else ""
    hint=sfont.render(f"WASD·Move  Shift·Sprint  Mouse·Aim  LMB/Space·Attack  {hint_map}  ESC·Quit",True,(70,60,50))
    surf.blit(hint,(SCREEN_W//2-hint.get_width()//2,SCREEN_H-20))
    # Stamina
    sr=player.stamina/player.STAMINA_MAX
    sc2=(ORANGE if player.stamina_locked==0 else (80,20,20))
    lbl="SPRINT" if player.stamina_locked==0 else "EXHAUSTED"
    _bar(surf,12,48,180,10,sr,sc2,lbl,sc2,sfont)
    # Battery
    br=player.battery/player.BATTERY_MAX
    bcol=CYAN if br>0.4 else (200,150,20) if br>0.15 else RED
    blbl="BATTERY"
    if player.battery_dead: bcol=DARK_RED; blbl="NO BATTERY — DANGER"
    _bar(surf,12,82,180,10,br,bcol,blbl,bcol,sfont)
    # Difficulty badge
    dc=DIFF_SETTINGS[diff]['color']; dn=DIFF_SETTINGS[diff]['name']
    dt=sfont.render(dn,True,dc)
    surf.blit(dt,(SCREEN_W//2-dt.get_width()//2,6))

def _bar(surf,bx,by,bw,bh,ratio,fill_col,label,label_col,sfont):
    pygame.draw.rect(surf,(30,25,20),(bx,by,bw,bh),border_radius=4)
    fw=int(bw*ratio)
    if fw>0: pygame.draw.rect(surf,fill_col,(bx,by,fw,bh),border_radius=4)
    pygame.draw.rect(surf,(80,70,55),(bx,by,bw,bh),1,border_radius=4)
    surf.blit(sfont.render(label,True,label_col),(bx,by-16))

# ── Screenshake ───────────────────────────────────────────────────────────────
class Screenshake:
    def __init__(self): self.trauma=0.0
    def add(self,v): self.trauma=min(1.0,self.trauma+v)
    def update(self): self.trauma=max(0.0,self.trauma-.04)
    def offset(self):
        s=self.trauma**2
        return int(random.uniform(-14,14)*s),int(random.uniform(-14,14)*s)

# ── Difficulty Select screen ───────────────────────────────────────────────────
class DifficultySelect:
    def __init__(self,fonts):
        self.font,self.big_font,self.sfont=fonts
        self.selected=DIFF_NORMAL
        self.done=False; self.t=0

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
            # Card bg
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
            # Name
            nf=pygame.font.SysFont("courier",32,bold=True)
            nt=nf.render(ds['name'],True,col)
            surf.blit(nt,(cx2+cw//2-nt.get_width()//2,cy2+20))
            # Divider
            pygame.draw.line(surf,(*col,120),(cx2+20,cy2+68),(cx2+cw-20,cy2+68),1)
            # Desc lines
            df2=pygame.font.SysFont("courier",17)
            for j,line in enumerate(ds['desc']):
                icon="+" if "No" not in line and "no" not in line else "-"
                ic=(80,200,80) if icon=="+" else (200,80,80)
                lt=df2.render(f"{icon} {line}",True,ic if selected else (120,110,100))
                surf.blit(lt,(cx2+18,cy2+88+j*38))
            # Arrow if selected
            if selected:
                af=pygame.font.SysFont("courier",28,bold=True)
                arr=af.render("▼ SELECTED ▼",True,col)
                surf.blit(arr,(cx2+cw//2-arr.get_width()//2,cy2+ch-45))

# ── Tutorial screen ───────────────────────────────────────────────────────────
class TutorialScreen:
    CARDS=[
        {"icon":"move","title":"MOVEMENT",
         "lines":["WASD to move.","Hold SHIFT to sprint —","stamina bar limits it."],"color":AMBER},
        {"icon":"light","title":"FLASHLIGHT & BATTERY",
         "lines":["Aim with the MOUSE.","Battery drains over time.","Collect cyan BATTERIES!"],"color":CYAN},
        {"icon":"lever","title":"OBJECTIVE",
         "lines":["Pull all levers","scattered in the building.","Then find the EXIT."],"color":GREEN},
        {"icon":"monster","title":"THE CREATURE",
         "lines":["It navigates around walls.","In the dark it moves FAST.","LMB / SPACE to fight back."],"color":RED},
    ]
    CARD_TIME=130; FADE=22
    def __init__(self,fonts):
        self.font,self.big_font,self.sfont=fonts
        self.idx=0; self.timer=0; self.done=False
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
        cw,ch=700,340; cx2,cy2=SCREEN_W//2-cw//2,SCREEN_H//2-ch//2
        panel=pygame.Surface((cw,ch),pygame.SRCALPHA)
        pygame.draw.rect(panel,(20,18,24,220),(0,0,cw,ch),border_radius=16)
        pygame.draw.rect(panel,(*col,80),(0,0,cw,ch),2,border_radius=16)
        pygame.draw.rect(panel,(*col,180),(0,0,6,ch),border_radius=4)
        panel.set_alpha(alpha); surf.blit(panel,(cx2,cy2))
        tf=pygame.font.SysFont("courier",38,bold=True)
        ts=tf.render(card["title"],True,col); ts.set_alpha(alpha)
        surf.blit(ts,(cx2+130,cy2+48))
        bf=pygame.font.SysFont("courier",20)
        for i,line in enumerate(card["lines"]):
            ls=bf.render(line,True,(200,190,170)); ls.set_alpha(alpha)
            surf.blit(ls,(cx2+130,cy2+118+i*40))
        pa=int(180*abs(math.sin((self.timer%40)/40*math.pi)))
        pt="ENTER to start" if self.idx==len(self.CARDS)-1 else "ENTER to skip / wait..."
        ps=pygame.font.SysFont("courier",16).render(pt,True,col); ps.set_alpha(pa)
        surf.blit(ps,(SCREEN_W//2-ps.get_width()//2,SCREEN_H-70))

# ── States ────────────────────────────────────────────────────────────────────
S_MENU='menu'; S_DIFFSEL='diff'; S_TUTORIAL='tut'
S_PLAY='play'; S_DEAD='dead'; S_WIN='win'

# ── Game ──────────────────────────────────────────────────────────────────────
class Game:
    NUM_BATTERIES_BASE=10

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("SHADOWS WITHIN")
        self.screen=pygame.display.set_mode((0,0),pygame.FULLSCREEN)
        global SCREEN_W,SCREEN_H,TILE_W,TILE_H,MMAP_W,MMAP_H,MMAP_X,MMAP_Y
        SCREEN_W,SCREEN_H=self.screen.get_size()
        TILE_W=SCREEN_W//COLS_MAP; TILE_H=SCREEN_H//ROWS_MAP
        MMAP_W=COLS_MAP*MMAP_SCALE; MMAP_H=ROWS_MAP*MMAP_SCALE
        MMAP_X=SCREEN_W-MMAP_W-12; MMAP_Y=40
        self.clock=pygame.time.Clock()
        self.font    =pygame.font.SysFont("courier",36,bold=True)
        self.big_font=pygame.font.SysFont("courier",72,bold=True)
        self.sfont   =pygame.font.SysFont("courier",18)
        self.bg_surf =pygame.Surface((SCREEN_W,SCREEN_H))
        self.state=S_MENU; self.shake=Screenshake()
        self.menu_t=0; self.map_big=False
        self.vignette=self._bake_vignette()
        self.tutorial=None; self.diff_select=None
        self.diff=DIFF_NORMAL
        self.sounds=SoundManager()
        self.setup_level()

    def _bake_vignette(self):
        v=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        cx,cy=SCREEN_W//2,SCREEN_H//2; mr=int(math.hypot(cx,cy))
        for r in range(mr,0,-3):
            pygame.draw.circle(v,(0,0,0,int(200*(1-r/mr)**1.8)),(cx,cy),r,3)
        return v

    def _place_items(self,n,used,pool):
        p=[f for f in pool if f not in used]; random.shuffle(p)
        result=[]
        for fc,fr in p:
            if len(result)>=n: break
            result.append((fc,fr)); used.add((fc,fr))
        return result

    def setup_level(self):
        d=DIFF_SETTINGS[self.diff]
        self.TOTAL_LEVERS=d['levers']
        self.has_map=d['has_map']
        self.walls=get_walls(); self.floors=safe_floor_tiles()
        mid=[f for f in self.floors if 2<=f[0]<=COLS_MAP-3 and 2<=f[1]<=ROWS_MAP-3]
        start=mid[len(mid)//5] if mid else self.floors[0]
        px,py=tile_center(*start)
        self.player=Player(px,py,self.diff)
        used={start}
        far=[f for f in self.floors if math.hypot(tile_center(*f)[0]-px,tile_center(*f)[1]-py)>300]
        mt=random.choice(far) if far else random.choice([f for f in self.floors if f!=start])
        self.monster=Monster(*tile_center(*mt),self.diff)
        # Levers across 5 zones
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
        # Batteries
        self.batteries=[]
        for fc,fr in self._place_items(d['num_batteries'],used,self.floors):
            self.batteries.append(Battery(*tile_center(fc,fr)))
        # Exit
        ep=[f for f in self.floors if f[0]>COLS_MAP*.55 and f[1]>ROWS_MAP*.55 and f not in used]
        if not ep: ep=[f for f in self.floors if f not in used]
        self.exit_pos=tile_center(*(random.choice(ep) if ep else self.floors[-1]))
        self.particles:List[Particle]=[]
        self.message=""; self.message_timer=0
        self.ambient_timer=random.randint(300,600)
        self.fl_angle=0.0; self._battery_warned=False
        self.map_big=False

    # ── Helpers ───────────────────────────────────────────────────────────────
    def burst(self,x,y,color,n=12):
        for _ in range(n):
            self.particles.append(Particle(x,y,color,
                vx=random.uniform(-3.5,3.5),vy=random.uniform(-3.5,1),
                life=random.randint(18,45),size=random.randint(2,5)))

    def show_msg(self,text,dur=130):
        self.message=text; self.message_timer=dur

    def draw_map(self):
        self.bg_surf.fill(DARK)
        for r,row in enumerate(LEVEL_MAP):
            for c,ch in enumerate(row):
                rect=pygame.Rect(c*TILE_W,r*TILE_H,TILE_W,TILE_H)
                if ch=='1':
                    pygame.draw.rect(self.bg_surf,WALL_C,rect)
                    pygame.draw.line(self.bg_surf,WALL_HL,rect.topleft,rect.topright,1)
                    pygame.draw.line(self.bg_surf,WALL_HL,rect.topleft,rect.bottomleft,1)
                else:
                    pygame.draw.rect(self.bg_surf,FLOOR_C,rect)
        ex,ey=self.exit_pos
        if self.player.levers>=self.TOTAL_LEVERS:
            t=pygame.time.get_ticks(); p2=int(12+math.sin(t*.005)*5)
            pygame.draw.circle(self.bg_surf,(0,80,50),(ex,ey),p2+4)
            pygame.draw.circle(self.bg_surf,GREEN,(ex,ey),p2)
            pygame.draw.circle(self.bg_surf,WHITE,(ex,ey),5)
        else:
            pygame.draw.circle(self.bg_surf,(15,40,30),(ex,ey),8)

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
        self.screen.blit(play_t,(SCREEN_W//2-play_t.get_width()//2,320))
        mx,my=pygame.mouse.get_pos()
        exit_t=self.font.render("[ EXIT ]",True,WHITE)
        ex2=SCREEN_W//2-exit_t.get_width()//2; ey2=395
        er=pygame.Rect(ex2-10,ey2-5,exit_t.get_width()+20,exit_t.get_height()+10)
        hov=er.collidepoint(mx,my)
        ec=(220,60,60) if hov else (140,30,30)
        if hov:
            pygame.draw.rect(self.screen,(60,10,10),er,border_radius=6)
            pygame.draw.rect(self.screen,(140,30,30),er,2,border_radius=6)
        self.screen.blit(self.font.render("[ EXIT ]",True,ec),(ex2,ey2))
        for i,line in enumerate(["Navigate the darkness · pull levers · find the exit.",
                                  "","WASD · Move   Shift · Sprint   Mouse · Aim",
                                  "LMB/Space · Attack   M · BigMap   ESC · Quit"]):
            t=self.sfont.render(line,True,(90,75,55) if line else (0,0,0))
            self.screen.blit(t,(SCREEN_W//2-t.get_width()//2,470+i*28))
        self.screen.blit(self.vignette,(0,0))
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                if er.collidepoint(e.pos): pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if e.key==pygame.K_RETURN:
                    self.diff_select=DifficultySelect((self.font,self.big_font,self.sfont))
                    self.state=S_DIFFSEL

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
            if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE:
                self.state=S_MENU
            ds.handle_event(e)

    # ── Tutorial ──────────────────────────────────────────────────────────────
    def run_tutorial(self):
        tut=self.tutorial; tut.update(); tut.draw(self.screen)
        if tut.done: self.state=S_PLAY; self.setup_level()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: self.state=S_MENU
            tut.handle_event(e)

    # ── Attack ────────────────────────────────────────────────────────────────
    def _try_attack(self):
        if self.player.try_attack(self.monster):
            self.monster.take_hit()
            self.burst(self.monster.x,self.monster.y,RED,14); self.shake.add(.35)
            self.show_msg("CREATURE HIT!" if self.monster.hp>0 else "CREATURE STAGGERED!",70)

    # ── Play ──────────────────────────────────────────────────────────────────
    def run_play(self):
        keys=pygame.key.get_pressed()
        dx=int(keys[pygame.K_d]or keys[pygame.K_RIGHT])-int(keys[pygame.K_a]or keys[pygame.K_LEFT])
        dy=int(keys[pygame.K_s]or keys[pygame.K_DOWN]) -int(keys[pygame.K_w]or keys[pygame.K_UP])
        sprinting=bool(keys[pygame.K_LSHIFT]or keys[pygame.K_RSHIFT])
        moving=self.player.move(dx,dy,self.walls,sprinting)
        self.sounds.maybe_step(moving and bool(dx or dy))

        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if e.key==pygame.K_m and self.has_map:
                    self.map_big=not self.map_big
                if e.key==pygame.K_SPACE: self._try_attack()
            if e.type==pygame.MOUSEBUTTONDOWN and e.button==1: self._try_attack()

        mx,my=pygame.mouse.get_pos()
        self.fl_angle=math.atan2(my-self.player.y,mx-self.player.x)

        prev_dead=self.player.battery_dead
        self.player.drain_battery()
        if self.player.battery_dead and not prev_dead:
            self.show_msg("BATTERY DEAD — IT CAN SMELL YOU NOW!",260)
            self.shake.add(.6); self.sounds.play('growl',1.5)
        ratio=self.player.battery/self.player.BATTERY_MAX
        if ratio<0.15 and not self._battery_warned and not self.player.battery_dead:
            self._battery_warned=True
            self.show_msg("⚡ BATTERY LOW — find a battery!",200)
        if ratio>0.2: self._battery_warned=False

        self.player.update()

        bat_r=self.player.battery/self.player.BATTERY_MAX
        fl_len=int(80+240*bat_r); fl_fov=int(25+55*bat_r); fl_alpha=int(120+110*bat_r)
        if self.player.battery_dead: fl_poly=[]
        else: fl_poly=cast_flashlight(self.player.pos,self.fl_angle,fl_fov,self.walls,fl_len,64)

        in_fl=(point_in_poly(self.monster.x,self.monster.y,fl_poly) if fl_poly else False)
        self.monster.update(self.player,self.walls,self.floors,in_fl,self.player.battery_dead)

        # Monster chase sound
        if self.monster.mode=='chase':
            self.sounds.play_growl()
            self.sounds.set_drone_volume(0.35+0.2*math.sin(pygame.time.get_ticks()*.003))

        for lv in self.levers:
            lv.update()
            if lv.check_collect(self.player):
                self.player.levers+=1
                self.burst(lv.x,lv.y,AMBER,16); self.shake.add(.12)
                self.sounds.play('lever')
                rem=self.TOTAL_LEVERS-self.player.levers
                self.show_msg(f"LEVER PULLED!  {rem} remaining." if rem
                              else "ALL LEVERS PULLED!  FIND THE EXIT!",200 if not rem else 130)

        for b in self.batteries:
            b.update()
            if b.check_collect(self.player):
                self.player.recharge(Battery.RECHARGE)
                self.player.battery_dead=False; self._battery_warned=False
                self.burst(b.x,b.y,CYAN,14); self.shake.add(.1)
                self.sounds.play('battery')
                self.show_msg("BATTERY RECHARGED!",110)

        ex,ey=self.exit_pos
        if self.player.levers>=self.TOTAL_LEVERS and math.hypot(ex-self.player.x,ey-self.player.y)<26:
            self.state=S_WIN; self.sounds.play('win')
        if self.player.hp<=0:
            self.state=S_DEAD; self.shake.add(1.0); self.sounds.play('die')

        self.ambient_timer-=1
        if self.ambient_timer<=0:
            self.ambient_timer=random.randint(280,560)
            self.show_msg(random.choice([
                "...footsteps behind you.","...a low growl in the dark.",
                "...something breathes nearby.","...the walls are watching.",
                "...scratching. Getting closer.","...don't look back."]),100)

        for p in self.particles: p.update()
        self.particles=[p for p in self.particles if p.alive()]
        if self.player.hurt_timer==79:
            self.burst(self.player.x,self.player.y,(255,40,40),14)
            self.shake.add(.55); self.sounds.play('hurt')
        self.shake.update()

        # ── Render ────────────────────────────────────────────────────────────
        self.draw_map()
        ox,oy=self.shake.offset()
        gs=pygame.Surface((SCREEN_W,SCREEN_H)); gs.blit(self.bg_surf,(0,0))
        for lv in self.levers: lv.draw(gs)
        for b  in self.batteries: b.draw(gs)
        self.monster.draw(gs,in_fl)
        self.player.draw(gs,self.fl_angle)
        for p in self.particles: p.draw(gs)

        # Darkness
        dark_surf=pygame.Surface((SCREEN_W,SCREEN_H))
        dark_surf.fill((0,0,0))
        amb_col=(18,8,8) if self.player.battery_dead else (14,10,4)
        pygame.draw.circle(dark_surf,amb_col,(int(self.player.x),int(self.player.y)),45)
        if fl_poly and len(fl_poly)>=3:
            pygame.draw.polygon(dark_surf,(255,0,255),fl_poly)
            dark_surf.set_colorkey((255,0,255))
            warm=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
            warm.fill((0,0,0,0))
            pygame.draw.polygon(warm,(255,200,120,max(0,fl_alpha-180)),fl_poly)
            gs.blit(warm,(0,0))
        else:
            dark_surf.set_colorkey(None)
        gs.blit(dark_surf,(0,0))

        if self.player.hurt_timer>0:
            hs=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
            hs.fill((190,0,0,min(int(110*self.player.hurt_timer/80),110)))
            gs.blit(hs,(0,0))

        gs.blit(self.vignette,(0,0))
        self.screen.blit(gs,(ox,oy))
        draw_hud(self.screen,self.player,self.sfont,self.TOTAL_LEVERS,self.diff,self.has_map,self.map_big)

        if self.has_map and not self.map_big:
            draw_minimap(self.screen,self.player,self.levers,self.batteries,
                         self.exit_pos,self.monster,self.TOTAL_LEVERS,self.sfont,big=False)
        if self.has_map and self.map_big:
            # Dim background
            dim=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
            dim.fill((0,0,0,140)); self.screen.blit(dim,(0,0))
            draw_minimap(self.screen,self.player,self.levers,self.batteries,
                         self.exit_pos,self.monster,self.TOTAL_LEVERS,self.sfont,big=True)

        if self.monster.mode=='chase' and (pygame.time.get_ticks()//400)%2==0:
            w=self.sfont.render("⚠  IT IS COMING  ⚠",True,RED)
            self.screen.blit(w,(SCREEN_W//2-w.get_width()//2,52))
        if self.player.battery_dead and (pygame.time.get_ticks()//600)%2==0:
            bd=self.sfont.render("NO LIGHT",True,DARK_RED)
            self.screen.blit(bd,(SCREEN_W//2-bd.get_width()//2,72))
        if self.message_timer>0:
            self.message_timer-=1
            a=min(255,self.message_timer*5)
            col=(min(255,int(AMBER[0]*a/255)),min(255,int(AMBER[1]*a/255)),0)
            mt=self.sfont.render(self.message,True,col)
            self.screen.blit(mt,(SCREEN_W//2-mt.get_width()//2,SCREEN_H//2-70))

    # ── Dead ──────────────────────────────────────────────────────────────────
    def run_dead(self):
        self.screen.fill((5,0,0))
        for txt,col,y in[("YOU DIED",BLOOD,SCREEN_H//2-70),
                         ("The darkness consumed you.",(110,35,35),SCREEN_H//2+10),
                         ("ENTER · try again    ESC · quit",(70,40,40),SCREEN_H//2+75)]:
            s=(self.big_font if "DIED" in txt else self.font if "darkness" in txt else self.sfont).render(txt,True,col)
            self.screen.blit(s,(SCREEN_W//2-s.get_width()//2,y))
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if e.key==pygame.K_RETURN: self.state=S_PLAY; self.setup_level()

    # ── Win ───────────────────────────────────────────────────────────────────
    def run_win(self):
        self.screen.fill((2,8,4))
        for txt,col,y in[("ESCAPED!",GREEN,SCREEN_H//2-70),
                         ("The nightmare ends... for now.",TEAL,SCREEN_H//2+10),
                         ("ENTER · play again    ESC · quit",(35,100,70),SCREEN_H//2+75)]:
            s=(self.big_font if "ESCAPED" in txt else self.font if "nightmare" in txt else self.sfont).render(txt,True,col)
            self.screen.blit(s,(SCREEN_W//2-s.get_width()//2,y))
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if e.key==pygame.K_RETURN: self.state=S_MENU

    # ── Loop ──────────────────────────────────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(FPS)
            if   self.state==S_MENU:    self.run_menu()
            elif self.state==S_DIFFSEL: self.run_diffsel()
            elif self.state==S_TUTORIAL:self.run_tutorial()
            elif self.state==S_PLAY:    self.run_play()
            elif self.state==S_DEAD:    self.run_dead()
            elif self.state==S_WIN:     self.run_win()
            pygame.display.flip()

if __name__=="__main__":
    Game().run()