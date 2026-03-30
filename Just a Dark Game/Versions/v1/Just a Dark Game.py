"""
SHADOWS WITHIN  —  Pygame Survival Horror
WASD=Move  Shift=Sprint  Mouse=Aim  LMB/Space=Attack  M=Map  ESC=Quit
Collect 10 levers, find the exit.  Watch your flashlight battery!
"""
import pygame, math, random, sys
from typing import List

# ── Screen ────────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 800
FPS = 60

# ── Colours ───────────────────────────────────────────────────────────────────
BLACK=(0,0,0); WHITE=(255,255,255); RED=(200,20,20); DARK_RED=(120,0,0)
AMBER=(255,180,40); DARK=(15,15,20); BLOOD=(140,0,0); GREEN=(30,180,30)
TEAL=(30,160,130); WALL_C=(45,42,48); WALL_HL=(60,56,65); FLOOR_C=(20,18,22)
CYAN=(40,220,220); ORANGE=(255,120,20); YELLOW=(255,230,60)

# ── Map ───────────────────────────────────────────────────────────────────────
# Every row begins and ends with '1'.  Row 0 and last row are solid walls.
# No '0' tile touches the top or bottom border, so no item can be unreachable.
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
TILE_W   = SCREEN_W // COLS_MAP   # ~38 px
TILE_H   = SCREEN_H // ROWS_MAP   # ~42 px

# ── Map helpers ───────────────────────────────────────────────────────────────
def get_walls():
    return [pygame.Rect(c*TILE_W, r*TILE_H, TILE_W, TILE_H)
            for r,row in enumerate(LEVEL_MAP)
            for c,ch in enumerate(row) if ch=='1']

def tile_center(c, r):
    return (c*TILE_W + TILE_W//2, r*TILE_H + TILE_H//2)

def is_floor(c, r):
    if r<=0 or r>=ROWS_MAP-1 or c<=0 or c>=COLS_MAP-1:
        return False
    return LEVEL_MAP[r][c] == '0'

def get_floor_tiles():
    """Interior '0' tiles only — never touches map border."""
    return [(c,r) for r in range(1,ROWS_MAP-1)
                  for c in range(1,COLS_MAP-1)
                  if LEVEL_MAP[r][c]=='0']

def is_reachable(c, r):
    """Flood-fill sanity: tile must be connected to at least one neighbour."""
    return any(is_floor(c+dc,r+dr) for dc,dr in [(1,0),(-1,0),(0,1),(0,-1)])

def safe_floor_tiles():
    """Floor tiles that have at least one open neighbour (never isolated)."""
    return [(c,r) for c,r in get_floor_tiles() if is_reachable(c,r)]

# ── Raycasting flashlight ─────────────────────────────────────────────────────
def cast_flashlight(pos, angle, fov_deg, walls, length=300, rays=64):
    half = math.radians(fov_deg/2)
    pts  = [pos]
    for i in range(rays+1):
        a  = angle - half + (2*half*i/rays)
        cdx, cdy = math.cos(a), math.sin(a)
        best = length
        for w in walls:
            tx1=(w.left  -pos[0])/cdx if cdx else float('inf')
            tx2=(w.right -pos[0])/cdx if cdx else float('inf')
            ty1=(w.top   -pos[1])/cdy if cdy else float('inf')
            ty2=(w.bottom-pos[1])/cdy if cdy else float('inf')
            tmin=max(min(tx1,tx2),min(ty1,ty2))
            tmax=min(max(tx1,tx2),max(ty1,ty2))
            if 0<tmin<tmax and tmin<best: best=tmin
        pts.append((pos[0]+cdx*best, pos[1]+cdy*best))
    return pts

def point_in_poly(x, y, poly):
    inside=False; j=len(poly)-1
    for i in range(len(poly)):
        xi,yi=poly[i]; xj,yj=poly[j]
        if ((yi>y)!=(yj>y)) and (x<(xj-xi)*(y-yi)/(yj-yi)+xi):
            inside=not inside
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
    WALK_SPEED   = 3.0
    SPRINT_SPEED = 5.2
    RADIUS=10; MAX_HP=5; ATTACK_RANGE=55; ATTACK_CD=40
    STAMINA_MAX=300; STAMINA_DRAIN=1; STAMINA_REGEN=0.5; STAMINA_LOCK=120

    # Battery: drains every frame the flashlight is on.
    # ~3600 frames = 60 s at 60 fps per full battery
    BATTERY_MAX   = 3600
    BATTERY_DRAIN = 1

    def __init__(self,x,y):
        self.x,self.y=float(x),float(y)
        self.hp=self.MAX_HP
        self.attack_timer=0; self.hurt_timer=0; self.levers=0
        self.stamina=float(self.STAMINA_MAX); self.stamina_locked=0
        self.is_sprinting=False
        self.battery=float(self.BATTERY_MAX)   # flashlight charge
        self.battery_dead=False                # True when battery==0

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

    def drain_battery(self):
        if self.battery>0:
            self.battery=max(0,self.battery-self.BATTERY_DRAIN)
            if self.battery==0 and not self.battery_dead:
                self.battery_dead=True
        # battery stays at 0 until recharged

    def recharge(self,amount=1800):
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
        if self.is_sprinting:
            pygame.draw.circle(surf,(60,30,0),self.pos,self.RADIUS+5)
        pygame.draw.circle(surf,(int(col[0]*.4),int(col[1]*.4),0),self.pos,self.RADIUS+3)
        pygame.draw.circle(surf,col,self.pos,self.RADIUS)
        ex=int(self.x+math.cos(fl_angle)*6); ey=int(self.y+math.sin(fl_angle)*6)
        pygame.draw.circle(surf,WHITE,(ex,ey),3)

# ── Monster ───────────────────────────────────────────────────────────────────
class Monster:
    RADIUS=15; MAX_HP=8
    PATROL_SPEED       = 1.6   # fast enough to visibly move around map
    CHASE_SPEED_NORMAL = 2.4
    CHASE_SPEED_DARK   = 5.0
    SEARCH_SPEED       = 1.8
    DETECT_RANGE  = 240
    HEAR_RANGE    = 110   # hears you from nearby corridors
    ATTACK_RANGE  = 24; ATTACK_CD=75

    def __init__(self,x,y):
        self.x,self.y=float(x),float(y); self.hp=self.MAX_HP
        self.mode='patrol'
        self.patrol_target=(x,y); self.patrol_timer=0
        self.search_timer=0; self.attack_timer=0; self.hurt_timer=0
        self.last_known=None
        self.angle=random.uniform(0,math.pi*2)

    @property
    def pos(self): return (int(self.x),int(self.y))
    @property
    def rect(self):
        r=self.RADIUS; return pygame.Rect(self.x-r,self.y-r,r*2,r*2)

    def new_patrol(self,floors,ppos=None):
        # Bias heavily toward the player's quadrant so it keeps finding you
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

    def update(self,player,walls,floors,in_fl,battery_dead):
        if self.attack_timer>0: self.attack_timer-=1
        if self.hurt_timer>0:   self.hurt_timer-=1

        dpx=player.x-self.x; dpy=player.y-self.y
        dist_p=math.hypot(dpx,dpy)

        # Detection: always hears if close; sees if in flashlight beam; or if battery dead, smells you
        can_detect=(dist_p<self.HEAR_RANGE
                    or (in_fl and dist_p<self.DETECT_RANGE)
                    or (battery_dead and dist_p<400))   # hunts you in the dark

        if can_detect:
            self.mode='chase'; self.last_known=(player.x,player.y)

        # Pick speed
        chase_spd=(self.CHASE_SPEED_DARK if battery_dead else self.CHASE_SPEED_NORMAL)

        if self.mode=='chase':
            speed=chase_spd; tx,ty=player.x,player.y
            if not can_detect:
                self.mode='search'; self.search_timer=random.randint(200,400)
        elif self.mode=='search' and self.last_known:
            speed=self.SEARCH_SPEED; tx,ty=self.last_known
            self.search_timer-=1
            if self.search_timer<=0: self.mode='patrol'
        else:
            self.mode='patrol'
            speed=self.PATROL_SPEED
            tx,ty=self.patrol_target; self.patrol_timer-=1
            if self.patrol_timer<=0 or math.hypot(tx-self.x,ty-self.y)<10:
                self.new_patrol(floors,(player.x,player.y))

        # ── Move: axis-separated so monster slides along walls instead of stopping ──
        dx=tx-self.x; dy=ty-self.y; dist=math.hypot(dx,dy)
        if dist>2:
            self.angle=math.atan2(dy,dx)
            nx,ny=dx/dist*speed, dy/dist*speed

            # Move X
            self.x+=nx
            for w in walls:
                if self.rect.colliderect(w):
                    if nx>0: self.x=w.left-self.RADIUS
                    else:    self.x=w.right+self.RADIUS

            # Move Y
            self.y+=ny
            for w in walls:
                if self.rect.colliderect(w):
                    if ny>0: self.y=w.top-self.RADIUS
                    else:    self.y=w.bottom+self.RADIUS

            # Final hard unstuck: if still inside a wall, push out on closest axis
            for w in walls:
                if self.rect.colliderect(w):
                    ox_r=w.right-(self.x-self.RADIUS); ox_l=(self.x+self.RADIUS)-w.left
                    oy_b=w.bottom-(self.y-self.RADIUS); oy_t=(self.y+self.RADIUS)-w.top
                    ox=ox_r if nx>=0 else ox_l
                    oy=oy_b if ny>=0 else oy_t
                    if ox<oy: self.x+=ox_r if nx>=0 else -ox_l
                    else:     self.y+=oy_b if ny>=0 else -oy_t

        if dist_p<self.ATTACK_RANGE and self.attack_timer==0:
            player.take_damage(); self.attack_timer=self.ATTACK_CD

    def take_hit(self): self.hp-=1; self.hurt_timer=20

    def draw(self,surf,in_fl):
        chasing=self.mode=='chase'
        if not in_fl:
            # Invisible unless chasing — show glowing eyes
            if chasing:
                gr=self.RADIUS+6+int(math.sin(pygame.time.get_ticks()*.01)*3)
                pygame.draw.circle(surf,(50,0,0),self.pos,gr)
                for s in [-1,1]:
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
                             (int(self.x+math.cos(a)*(self.RADIUS+5)),
                              int(self.y+math.sin(a)*(self.RADIUS+5))),1)
        for s in [-1,1]:
            ex=int(self.x+math.cos(self.angle)*7+math.sin(self.angle)*5*s)
            ey=int(self.y+math.sin(self.angle)*7-math.cos(self.angle)*5*s)
            pygame.draw.circle(surf,RED,(ex,ey),4)
            pygame.draw.circle(surf,(255,100,100),(ex,ey),2)
        bw=32; filled=int(bw*self.hp/self.MAX_HP)
        bx,by=int(self.x-bw//2),int(self.y-self.RADIUS-9)
        pygame.draw.rect(surf,DARK_RED,(bx,by,bw,4))
        pygame.draw.rect(surf,RED,(bx,by,filled,4))

# ── Lever (formerly Fuse) ─────────────────────────────────────────────────────
class Lever:
    def __init__(self,x,y):
        self.x,self.y=int(x),int(y); self.collected=False
        self.bob=random.uniform(0,math.pi*2); self.pulse=random.uniform(0,math.pi*2)

    def update(self): self.bob+=.05; self.pulse+=.08

    def draw(self,surf):
        if self.collected: return
        cy=int(self.y+math.sin(self.bob)*4)
        cx=self.x
        # Glow
        gr=int(16+math.sin(self.pulse)*4)
        glow=pygame.Surface((gr*2+4,gr*2+4),pygame.SRCALPHA)
        pygame.draw.circle(glow,(255,200,40,50),(gr+2,gr+2),gr)
        surf.blit(glow,(cx-gr-2,cy-gr-2))
        # Lever shaft
        pygame.draw.rect(surf,(100,80,20),(cx-3,cy-8,6,14),border_radius=2)
        # Lever handle
        pygame.draw.circle(surf,AMBER,(cx,cy-8),5)
        pygame.draw.circle(surf,WHITE,(cx,cy-8),2)
        # Base
        pygame.draw.rect(surf,(140,110,30),(cx-7,cy+4,14,5),border_radius=2)

    def check_collect(self,player):
        if self.collected: return False
        if math.hypot(self.x-player.x,self.y-player.y)<22:
            self.collected=True; return True
        return False

# ── Battery pickup ────────────────────────────────────────────────────────────
class Battery:
    RECHARGE = 2400   # frames added (40 s)

    def __init__(self,x,y):
        self.x,self.y=int(x),int(y); self.collected=False
        self.pulse=random.uniform(0,math.pi*2)

    def update(self): self.pulse+=.06

    def draw(self,surf):
        if self.collected: return
        cx,cy=self.x,self.y
        p=math.sin(self.pulse)
        gr=int(14+p*4)
        glow=pygame.Surface((gr*2+4,gr*2+4),pygame.SRCALPHA)
        pygame.draw.circle(glow,(40,220,220,45),(gr+2,gr+2),gr)
        surf.blit(glow,(cx-gr-2,cy-gr-2))
        # Battery body
        pygame.draw.rect(surf,(20,80,90),(cx-7,cy-5,14,10),border_radius=2)
        pygame.draw.rect(surf,CYAN,(cx-6,cy-4,12,8),border_radius=1)
        # Positive nub
        pygame.draw.rect(surf,CYAN,(cx+7,cy-2,3,4),border_radius=1)
        # Lightning bolt
        f=pygame.font.SysFont("courier",9,bold=True)
        t=f.render("+",True,WHITE)
        surf.blit(t,(cx-t.get_width()//2,cy-t.get_height()//2))

    def check_collect(self,player):
        if self.collected: return False
        if math.hypot(self.x-player.x,self.y-player.y)<22:
            self.collected=True; return True
        return False

# ── Minimap ───────────────────────────────────────────────────────────────────
MMAP_SCALE=6
MMAP_W=COLS_MAP*MMAP_SCALE; MMAP_H=ROWS_MAP*MMAP_SCALE
MMAP_X=SCREEN_W-MMAP_W-12;  MMAP_Y=40

def draw_minimap(surf,player,levers,batteries,exit_pos,monster,total_levers,sfont):
    mm=pygame.Surface((MMAP_W,MMAP_H),pygame.SRCALPHA)
    mm.fill((0,0,0,160))
    for r,row in enumerate(LEVEL_MAP):
        for c,ch in enumerate(row):
            col=(70,65,80,220) if ch=='1' else (30,28,35,180)
            pygame.draw.rect(mm,col,(c*MMAP_SCALE,r*MMAP_SCALE,MMAP_SCALE,MMAP_SCALE))

    # Exit
    if player.levers>=total_levers:
        ex_mm=int(exit_pos[0]/TILE_W*MMAP_SCALE); ey_mm=int(exit_pos[1]/TILE_H*MMAP_SCALE)
        pygame.draw.circle(mm,GREEN,(ex_mm,ey_mm),4)

    tick=pygame.time.get_ticks()

    # Levers — blinking amber
    for lv in levers:
        if not lv.collected:
            blink=(tick//500)%2==0
            lx=int(lv.x/TILE_W*MMAP_SCALE); ly=int(lv.y/TILE_H*MMAP_SCALE)
            pygame.draw.circle(mm,AMBER if blink else (180,120,20),(lx,ly),3)

    # Batteries — cyan dot
    for b in batteries:
        if not b.collected:
            bx2=int(b.x/TILE_W*MMAP_SCALE); by2=int(b.y/TILE_H*MMAP_SCALE)
            pygame.draw.circle(mm,CYAN,(bx2,by2),3)

    # Monster — pulsing radar ring + dot
    mx_mm=int(monster.x/TILE_W*MMAP_SCALE); my_mm=int(monster.y/TILE_H*MMAP_SCALE)
    ping=(tick%1200)/1200.0
    ring_r=int(2+ping*12); ring_a=int(255*(1-ping))
    if ring_a>10:
        rs=pygame.Surface((MMAP_W,MMAP_H),pygame.SRCALPHA)
        pygame.draw.circle(rs,(200,0,0,ring_a),(mx_mm,my_mm),ring_r,1)
        mm.blit(rs,(0,0))
    dot_col=RED if monster.mode=='chase' else (130,25,25)
    pygame.draw.circle(mm,dot_col,(mx_mm,my_mm),3)

    # Player
    px_mm=int(player.x/TILE_W*MMAP_SCALE); py_mm=int(player.y/TILE_H*MMAP_SCALE)
    pygame.draw.circle(mm,AMBER,(px_mm,py_mm),3)

    surf.blit(mm,(MMAP_X,MMAP_Y))
    pygame.draw.rect(surf,(80,70,60),(MMAP_X-1,MMAP_Y-1,MMAP_W+2,MMAP_H+2),1)
    surf.blit(sfont.render("MAP [M]",True,(90,80,60)),(MMAP_X,MMAP_Y-15))
    legend=sfont.render("▪lever  ▪battery  ▪monster",True,(90,80,55))
    surf.blit(legend,(MMAP_X,MMAP_Y+MMAP_H+2))

# ── HUD ───────────────────────────────────────────────────────────────────────
def heart_pts(cx,cy,r):
    pts=[]
    for i in range(60):
        t=i/60*math.pi*2
        pts.append((cx+r*(16*math.sin(t)**3)/16,
                    cy-r*(13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t))/16))
    return pts

def draw_hud(surf,player,sfont,total_levers):
    # Hearts
    for i in range(player.MAX_HP):
        pygame.draw.polygon(surf,RED if i<player.hp else (50,20,20),heart_pts(22+i*30,22,10))

    # Lever counter
    lc=sfont.render(f"LEVERS  {player.levers}/{total_levers}",True,AMBER)
    surf.blit(lc,(SCREEN_W-210,10))

    # Controls
    hint=sfont.render("WASD·Move  Shift·Sprint  Mouse·Aim  LMB/Space·Attack  M·Map",True,(70,60,50))
    surf.blit(hint,(SCREEN_W//2-hint.get_width()//2,SCREEN_H-20))

    # Stamina bar
    _bar(surf,12,48,160,10,player.stamina/player.STAMINA_MAX,
         ORANGE if player.stamina_locked==0 else (80,20,20),
         "SPRINT" if player.stamina_locked==0 else "EXHAUSTED",
         (180,120,30) if player.stamina_locked==0 else (150,30,30),sfont)

    # Battery bar
    ratio=player.battery/player.BATTERY_MAX
    if ratio>0.4:    bcol=CYAN
    elif ratio>0.15: bcol=(200,150,20)
    else:            bcol=RED
    label="BATTERY"
    if player.battery_dead:
        bcol=DARK_RED; label="NO BATTERY — DANGER"
    _bar(surf,12,82,160,10,ratio,bcol,label,bcol,sfont)

def _bar(surf,bx,by,bw,bh,ratio,fill_col,label,label_col,sfont):
    pygame.draw.rect(surf,(30,25,20),(bx,by,bw,bh),border_radius=4)
    fw=int(bw*ratio)
    if fw>0: pygame.draw.rect(surf,fill_col,(bx,by,fw,bh),border_radius=4)
    pygame.draw.rect(surf,(80,70,55),(bx,by,bw,bh),1,border_radius=4)
    lbl=sfont.render(label,True,label_col)
    surf.blit(lbl,(bx,by-16))

# ── Screenshake ───────────────────────────────────────────────────────────────
class Screenshake:
    def __init__(self): self.trauma=0.0
    def add(self,v): self.trauma=min(1.0,self.trauma+v)
    def update(self): self.trauma=max(0.0,self.trauma-.04)
    def offset(self):
        s=self.trauma**2
        return int(random.uniform(-14,14)*s),int(random.uniform(-14,14)*s)

# ── Tutorial ──────────────────────────────────────────────────────────────────
class TutorialScreen:
    CARDS=[
        {"icon":"move",    "title":"MOVEMENT",
         "lines":["WASD to move.","Hold SHIFT to sprint —","stamina bar limits it."],"color":AMBER},
        {"icon":"light",   "title":"FLASHLIGHT & BATTERY",
         "lines":["Aim with the MOUSE.","Battery drains over time.","Collect cyan BATTERIES to recharge!"],"color":CYAN},
        {"icon":"lever",   "title":"OBJECTIVE",
         "lines":["Pull all 10 LEVERS","scattered in the building.","Then find the EXIT."],"color":GREEN},
        {"icon":"monster", "title":"THE CREATURE",
         "lines":["It patrols — and gets closer.","In the dark it moves FAST.","LMB / SPACE to fight back."],"color":RED},
    ]
    CARD_TIME=130; FADE=22

    def __init__(self,fonts):
        self.font,self.big_font,self.sfont=fonts
        self.idx=0; self.timer=0; self.done=False

    def _alpha(self):
        t=self.timer; T=self.CARD_TIME; F=self.FADE
        if t<F:         return int(255*t/F)
        if t>T-F:       return int(255*(T-t)/F)
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
        # Progress dots
        for i in range(len(self.CARDS)):
            pygame.draw.circle(surf,col if i==self.idx else (50,45,40),
                               (SCREEN_W//2-(len(self.CARDS)-1)*20+i*40,80),6)
        # Panel
        cw,ch=700,340; cx2,cy2=SCREEN_W//2-cw//2,SCREEN_H//2-ch//2
        panel=pygame.Surface((cw,ch),pygame.SRCALPHA)
        pygame.draw.rect(panel,(20,18,24,220),(0,0,cw,ch),border_radius=16)
        pygame.draw.rect(panel,(*col,80),(0,0,cw,ch),2,border_radius=16)
        pygame.draw.rect(panel,(*col,180),(0,0,6,ch),border_radius=4)
        panel.set_alpha(alpha)
        # Icon
        ic=card["icon"]; icx,icy=62,ch//2
        if   ic=="move":    _icon_wasd(panel,icx,icy,col)
        elif ic=="light":   _icon_flashlight(panel,icx,icy,col)
        elif ic=="lever":   _icon_lever(panel,icx,icy,col)
        elif ic=="monster": _icon_monster(panel,icx,icy,col)
        surf.blit(panel,(cx2,cy2))
        # Text
        tf=pygame.font.SysFont("courier",38,bold=True)
        ts=tf.render(card["title"],True,col); ts.set_alpha(alpha)
        surf.blit(ts,(cx2+130,cy2+48))
        bf=pygame.font.SysFont("courier",20)
        for i,line in enumerate(card["lines"]):
            ls=bf.render(line,True,(200,190,170)); ls.set_alpha(alpha)
            surf.blit(ls,(cx2+130,cy2+118+i*40))
        # Prompt
        pa=int(180*abs(math.sin((self.timer%40)/40*math.pi)))
        pt="ENTER to start" if self.idx==len(self.CARDS)-1 else "ENTER to skip / wait..."
        ps=pygame.font.SysFont("courier",16).render(pt,True,col); ps.set_alpha(pa)
        surf.blit(ps,(SCREEN_W//2-ps.get_width()//2,SCREEN_H-70))

def _icon_wasd(s,cx,cy,col):
    f=pygame.font.SysFont("courier",14,bold=True)
    for label,ox,oy in[("W",-1,-2),("A",-2,-1),("S",-1,-1),("D",0,-1)]:
        r=pygame.Rect(cx+ox*22-10,cy+oy*22-10,20,20)
        pygame.draw.rect(s,(50,45,40),r,border_radius=3)
        pygame.draw.rect(s,col,r,1,border_radius=3)
        t=f.render(label,True,col)
        s.blit(t,(r.x+r.w//2-t.get_width()//2,r.y+r.h//2-t.get_height()//2))
    rs=pygame.Rect(cx-34,cy+14,68,16)
    pygame.draw.rect(s,(50,45,40),rs,border_radius=3)
    pygame.draw.rect(s,ORANGE,rs,1,border_radius=3)
    ts=f.render("SHIFT",True,ORANGE)
    s.blit(ts,(rs.x+rs.w//2-ts.get_width()//2,rs.y+rs.h//2-ts.get_height()//2))

def _icon_flashlight(s,cx,cy,col):
    for i in range(21):
        a=-0.52+0.052*i
        pygame.draw.line(s,(*col,80),(cx,cy),(int(cx+math.cos(a)*55),int(cy+math.sin(a)*55)),2)
    pygame.draw.circle(s,col,(cx,cy),6)
    # little battery icon
    pygame.draw.rect(s,col,(cx+18,cy-8,18,12),border_radius=2)
    pygame.draw.rect(s,col,(cx+36,cy-4,4,4),border_radius=1)

def _icon_lever(s,cx,cy,col):
    for i in range(5):
        a=i/5*math.pi*2-math.pi/2
        x=int(cx+math.cos(a)*30); y=int(cy+math.sin(a)*30)
        pygame.draw.rect(s,(80,60,10),(x-3,y-6,6,12),border_radius=2)
        pygame.draw.circle(s,col,(x,y-6),5)
        pygame.draw.circle(s,WHITE,(x,y-6),2)

def _icon_monster(s,cx,cy,col):
    pygame.draw.circle(s,(60,10,10),(cx,cy),22)
    pygame.draw.circle(s,col,(cx,cy),20)
    t=pygame.time.get_ticks()
    for i in range(8):
        a=i*math.pi/4+t*.002
        pygame.draw.line(s,(100,10,10),(cx,cy),(int(cx+math.cos(a)*28),int(cy+math.sin(a)*28)),1)
    for ss in[-1,1]:
        pygame.draw.circle(s,(255,50,50),(cx+8*ss,cy-5),4)
        pygame.draw.circle(s,WHITE,(cx+8*ss,cy-5),2)

# ── States ────────────────────────────────────────────────────────────────────
S_MENU='menu'; S_TUTORIAL='tut'; S_PLAY='play'; S_DEAD='dead'; S_WIN='win'

# ── Game ──────────────────────────────────────────────────────────────────────
class Game:
    TOTAL_LEVERS = 10
    NUM_BATTERIES = 5

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("SHADOWS WITHIN")
        self.screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
        self.clock=pygame.time.Clock()
        self.font    =pygame.font.SysFont("courier",36,bold=True)
        self.big_font=pygame.font.SysFont("courier",72,bold=True)
        self.sfont   =pygame.font.SysFont("courier",16)
        self.darkness=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        self.bg_surf =pygame.Surface((SCREEN_W,SCREEN_H))
        self.state=S_MENU; self.shake=Screenshake()
        self.menu_t=0; self.show_map=True
        self.vignette=self._bake_vignette()
        self.tutorial=None
        self.setup_level()

    def _bake_vignette(self):
        v=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        cx,cy=SCREEN_W//2,SCREEN_H//2; mr=int(math.hypot(cx,cy))
        for r in range(mr,0,-3):
            pygame.draw.circle(v,(0,0,0,int(200*(1-r/mr)**1.8)),(cx,cy),r,3)
        return v

    def _place_items(self, n, used, floors_pool):
        """Pick n unique safe floor tiles not already in 'used'."""
        pool = [f for f in floors_pool if f not in used]
        random.shuffle(pool)
        result = []
        for fc, fr in pool:
            if len(result) >= n:
                break
            result.append((fc, fr))
            used.add((fc, fr))
        return result

    def setup_level(self):
        self.walls =get_walls()
        self.floors=safe_floor_tiles()   # interior + reachable only

        # Player start — pick a tile well inside the map
        mid_tiles=[f for f in self.floors
                   if 2<=f[0]<=COLS_MAP-3 and 2<=f[1]<=ROWS_MAP-3]
        start=mid_tiles[len(mid_tiles)//5] if mid_tiles else self.floors[0]
        px,py=tile_center(*start)
        self.player=Player(px,py)

        used={start}

        # Monster start — far from player, on a guaranteed safe tile, NOT added to used
        far=[f for f in self.floors if math.hypot(tile_center(*f)[0]-px,tile_center(*f)[1]-py)>300]
        monster_tile=random.choice(far) if far else random.choice([f for f in self.floors if f!=start])
        mx,my=tile_center(*monster_tile)
        self.monster=Monster(mx,my)
        # Note: monster tile intentionally NOT added to used — items can share its tile

        # Levers — spread across 5 zones
        self.levers=[]
        zones=[
            [f for f in self.floors if f[0]< COLS_MAP//3  and f[1]< ROWS_MAP//2],
            [f for f in self.floors if COLS_MAP//3<=f[0]<2*COLS_MAP//3 and f[1]< ROWS_MAP//2],
            [f for f in self.floors if f[0]>=2*COLS_MAP//3 and f[1]< ROWS_MAP//2],
            [f for f in self.floors if f[0]< COLS_MAP//2  and f[1]>=ROWS_MAP//2],
            [f for f in self.floors if f[0]>=COLS_MAP//2  and f[1]>=ROWS_MAP//2],
        ]
        per_zone=self.TOTAL_LEVERS//len(zones)
        extra_zone=self.TOTAL_LEVERS%len(zones)
        for zi,zone in enumerate(zones):
            n=per_zone+(1 if zi<extra_zone else 0)
            placed=self._place_items(n,used,zone)
            for fc,fr in placed:
                cx2,cy2=tile_center(fc,fr); self.levers.append(Lever(cx2,cy2))
        # Fallback if a zone was tiny
        if len(self.levers)<self.TOTAL_LEVERS:
            extra=self._place_items(self.TOTAL_LEVERS-len(self.levers),used,self.floors)
            for fc,fr in extra:
                cx2,cy2=tile_center(fc,fr); self.levers.append(Lever(cx2,cy2))

        # Batteries — scattered across map
        self.batteries=[]
        bat_tiles=self._place_items(self.NUM_BATTERIES,used,self.floors)
        for fc,fr in bat_tiles:
            cx2,cy2=tile_center(fc,fr); self.batteries.append(Battery(cx2,cy2))

        # Exit — bottom-right area, not too close to start
        exit_pool=[f for f in self.floors
                   if f[0]>COLS_MAP*0.55 and f[1]>ROWS_MAP*0.55 and f not in used]
        if not exit_pool:
            exit_pool=[f for f in self.floors if f not in used]
        ef=random.choice(exit_pool) if exit_pool else self.floors[-1]
        self.exit_pos=tile_center(*ef)

        self.particles:List[Particle]=[]
        self.message=""; self.message_timer=0
        self.ambient_timer=random.randint(300,600)
        self.fl_angle=0.0
        self._battery_warned=False

    # ── Helpers ───────────────────────────────────────────────
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

    # ── Menu ──────────────────────────────────────────────────
    def run_menu(self):
        self.menu_t+=1; self.screen.fill((4,2,6))
        flicker=1.0 if random.random()>.015 else random.uniform(.3,.7); rv=int(210*flicker)
        t1=self.big_font.render("SHADOWS",True,(rv,8,8))
        t2=self.big_font.render("WITHIN", True,(rv,rv//6,8))
        self.screen.blit(t1,(SCREEN_W//2-t1.get_width()//2,100))
        self.screen.blit(t2,(SCREEN_W//2-t2.get_width()//2,178))
        pr=int(190*abs(math.sin(self.menu_t*.035)))
        p2=self.font.render("[ PRESS ENTER ]",True,(pr,int(pr*.55),0))
        self.screen.blit(p2,(SCREEN_W//2-p2.get_width()//2,320))
        for i,line in enumerate(["Pull 10 levers · find the exit · watch your battery.",
                                  "","WASD · Move   Shift · Sprint   Mouse · Aim",
                                  "LMB/Space · Attack   M · Map   ESC · Quit"]):
            t=self.sfont.render(line,True,(90,75,55) if line else (0,0,0))
            self.screen.blit(t,(SCREEN_W//2-t.get_width()//2,420+i*26))
        self.screen.blit(self.vignette,(0,0))
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if e.key==pygame.K_RETURN:
                    self.tutorial=TutorialScreen((self.font,self.big_font,self.sfont))
                    self.state=S_TUTORIAL

    # ── Tutorial ──────────────────────────────────────────────
    def run_tutorial(self):
        tut=self.tutorial; tut.update(); tut.draw(self.screen)
        if tut.done: self.state=S_PLAY; self.setup_level()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
            tut.handle_event(e)

    # ── Attack ────────────────────────────────────────────────
    def _try_attack(self):
        if self.player.try_attack(self.monster):
            self.monster.take_hit()
            self.burst(self.monster.x,self.monster.y,RED,14); self.shake.add(.35)
            self.show_msg("CREATURE HIT!" if self.monster.hp>0 else "CREATURE STAGGERED!",70)

    # ── Play ──────────────────────────────────────────────────
    def run_play(self):
        keys=pygame.key.get_pressed()
        dx=int(keys[pygame.K_d]or keys[pygame.K_RIGHT])-int(keys[pygame.K_a]or keys[pygame.K_LEFT])
        dy=int(keys[pygame.K_s]or keys[pygame.K_DOWN]) -int(keys[pygame.K_w]or keys[pygame.K_UP])
        sprinting=bool(keys[pygame.K_LSHIFT]or keys[pygame.K_RSHIFT])
        self.player.move(dx,dy,self.walls,sprinting)

        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if e.key==pygame.K_m: self.show_map=not self.show_map
                if e.key==pygame.K_SPACE: self._try_attack()
            if e.type==pygame.MOUSEBUTTONDOWN and e.button==1: self._try_attack()

        mx,my=pygame.mouse.get_pos()
        self.fl_angle=math.atan2(my-self.player.y,mx-self.player.x)

        # Battery drain
        prev_dead=self.player.battery_dead
        self.player.drain_battery()
        if self.player.battery_dead and not prev_dead:
            self.show_msg("BATTERY DEAD — IT CAN SMELL YOU NOW!",260)
            self.shake.add(.6)
        # Low battery warning
        ratio=self.player.battery/self.player.BATTERY_MAX
        if ratio<0.15 and not self._battery_warned and not self.player.battery_dead:
            self._battery_warned=True
            self.show_msg("⚡ BATTERY LOW — find a battery!",200)
        if ratio>0.2: self._battery_warned=False

        self.player.update()

        # Flashlight: shrink beam as battery fades
        bat_r=self.player.battery/self.player.BATTERY_MAX
        fl_len  =int(80  + 240*bat_r)   # 80px dead → 320px full
        fl_fov  =int(25  + 55 *bat_r)   # 25° dead → 80° full
        fl_alpha=int(120 + 110*bat_r)   # dimmer when low (120→230)

        if self.player.battery_dead:
            fl_poly=[]  # no light at all
        else:
            fl_poly=cast_flashlight(self.player.pos,self.fl_angle,fl_fov,self.walls,fl_len,64)

        in_fl=(point_in_poly(self.monster.x,self.monster.y,fl_poly)
               if fl_poly else False)
        self.monster.update(self.player,self.walls,self.floors,in_fl,self.player.battery_dead)

        # Levers
        for lv in self.levers:
            lv.update()
            if lv.check_collect(self.player):
                self.player.levers+=1
                self.burst(lv.x,lv.y,AMBER,16); self.shake.add(.12)
                rem=self.TOTAL_LEVERS-self.player.levers
                self.show_msg(f"LEVER PULLED!  {rem} remaining." if rem
                              else "ALL LEVERS PULLED!  FIND THE EXIT!",
                              200 if not rem else 130)

        # Batteries
        for b in self.batteries:
            b.update()
            if b.check_collect(self.player):
                self.player.recharge(Battery.RECHARGE)
                self.player.battery_dead=False
                self._battery_warned=False
                self.burst(b.x,b.y,CYAN,14); self.shake.add(.1)
                self.show_msg("BATTERY RECHARGED!",110)

        # Exit
        ex,ey=self.exit_pos
        if (self.player.levers>=self.TOTAL_LEVERS
                and math.hypot(ex-self.player.x,ey-self.player.y)<26):
            self.state=S_WIN

        if self.player.hp<=0:
            self.state=S_DEAD; self.shake.add(1.0)

        # Ambient
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
            self.burst(self.player.x,self.player.y,(255,40,40),14); self.shake.add(.55)
        self.shake.update()

        # ── Render ────────────────────────────────────────────
        self.draw_map()
        ox,oy=self.shake.offset()
        gs=pygame.Surface((SCREEN_W,SCREEN_H)); gs.blit(self.bg_surf,(0,0))

        for lv in self.levers:  lv.draw(gs)
        for b  in self.batteries: b.draw(gs)
        self.monster.draw(gs,in_fl)
        self.player.draw(gs,self.fl_angle)
        for p in self.particles: p.draw(gs)

        # ── Darkness overlay ─────────────────────────────────────
        # Correct method: draw darkness on a surface, punch the flashlight
        # cone as a "clear" hole using a colorkey.
        dark_surf = pygame.Surface((SCREEN_W, SCREEN_H))
        dark_surf.fill((0, 0, 0))

        # Ambient circle around player — draw slightly lighter so player
        # can always see their immediate surroundings (even battery dead)
        amb_col = (18, 8, 8) if self.player.battery_dead else (14, 10, 4)
        pygame.draw.circle(dark_surf, amb_col,
                           (int(self.player.x), int(self.player.y)), 45)

        if fl_poly and len(fl_poly) >= 3:
            # Use MAGENTA as colorkey — draw cone in magenta, set colorkey,
            # blit dark_surf onto gs: magenta areas = transparent = player sees through
            pygame.draw.polygon(dark_surf, (255, 0, 255), fl_poly)
            dark_surf.set_colorkey((255, 0, 255))
            # Also set ambient circle to colorkey so it shows through too
            # (already drawn as dark, just let the map show through the cone)

            # Warm cone tint directly on gs before we overlay darkness
            warm = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            warm.fill((0, 0, 0, 0))
            pygame.draw.polygon(warm, (255, 200, 120, max(0, fl_alpha - 180)), fl_poly)
            gs.blit(warm, (0, 0))
        else:
            dark_surf.set_colorkey(None)

        gs.blit(dark_surf, (0, 0))

        if self.player.hurt_timer>0:
            hs=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
            hs.fill((190,0,0,min(int(110*self.player.hurt_timer/80),110)))
            gs.blit(hs,(0,0))

        gs.blit(self.vignette,(0,0))
        self.screen.blit(gs,(ox,oy))

        draw_hud(self.screen,self.player,self.sfont,self.TOTAL_LEVERS)

        if self.show_map:
            draw_minimap(self.screen,self.player,self.levers,self.batteries,
                         self.exit_pos,self.monster,self.TOTAL_LEVERS,self.sfont)

        # Chase warning
        if self.monster.mode=='chase' and (pygame.time.get_ticks()//400)%2==0:
            w=self.sfont.render("⚠  IT IS COMING  ⚠",True,RED)
            self.screen.blit(w,(SCREEN_W//2-w.get_width()//2,52))

        # Battery dead overlay message
        if self.player.battery_dead and (pygame.time.get_ticks()//600)%2==0:
            bd=self.sfont.render("NO LIGHT",True,DARK_RED)
            self.screen.blit(bd,(SCREEN_W//2-bd.get_width()//2,72))

        if self.message_timer>0:
            self.message_timer-=1
            a=min(255,self.message_timer*5)
            col=(min(255,int(AMBER[0]*a/255)),min(255,int(AMBER[1]*a/255)),0)
            mt=self.sfont.render(self.message,True,col)
            self.screen.blit(mt,(SCREEN_W//2-mt.get_width()//2,SCREEN_H//2-70))

    # ── Dead / Win ────────────────────────────────────────────
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
                if e.key==pygame.K_RETURN: self.state=S_PLAY; self.setup_level()

    def run(self):
        while True:
            self.clock.tick(FPS)
            if   self.state==S_MENU:     self.run_menu()
            elif self.state==S_TUTORIAL: self.run_tutorial()
            elif self.state==S_PLAY:     self.run_play()
            elif self.state==S_DEAD:     self.run_dead()
            elif self.state==S_WIN:      self.run_win()
            pygame.display.flip()

if __name__=="__main__":
    Game().run()