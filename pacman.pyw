#! /usr/bin/python
# Code taken from https://github.com/greyblue9/pacman-python

# pacman.pyw
# By David Reilly

# Modified by Andy Sommerville, 8 October 2007:
# - Changed hard-coded DOS paths to os.path calls
# - Added constant SCRIPT_PATH (so you don't need to have pacman.pyw and res in your cwd, as long
# -   as those two are in the same directory)
# - Changed text-file reading to accomodate any known EOLn method (\n, \r, or \r\n)
# - I (happily) don't have a Windows box to test this. Blocks marked "WIN???"
# -   should be examined if this doesn't run in Windows
# - Added joystick support (configure by changing JS_* constants)
# - Added a high-score list. Depends on wx for querying the user's name

# Modified by Ethan Jung, 2018
# - Added code from Tensorflow/Tflearn to create a pacman AI
# - Uses a DNN with convoluted and fully connected layers to crreate the model
# - Changed the code from python2 to python3
# - Fixed some issues with recursion

import pygame, sys, os, random, math
from pygame.locals import *
import numpy as np
import tflearn
import tensorflow as tf

# WIN???
SCRIPT_PATH=sys.path[0]

# NO_GIF_TILES -- tile numbers which do not correspond to a GIF file
# currently only "23" for the high-score list
NO_GIF_TILES=[23]

NO_WX=0 # if set, the high-score code will not attempt to ask the user his name
USER_NAME="User" # USER_NAME=os.getlogin() # the default user name if wx fails to load or NO_WX

# Joystick defaults - maybe add a Preferences dialog in the future?
JS_DEVNUM=0 # device 0 (pygame joysticks always start at 0). if JS_DEVNUM is not a valid device, will use 0
JS_XAXIS=0 # axis 0 for left/right (default for most joysticks)
JS_YAXIS=1 # axis 1 for up/down (default for most joysticks)
JS_STARTBUTTON=0 # button number to start the game. this is a matter of personal preference, and will vary from device to device

# Must come before pygame.init()
pygame.mixer.pre_init(22050,16,2,512)
JS_STARTBUTTON=0 # button number to start the game. this is a matter of personal preference, and will vary from device to device
pygame.mixer.init()

clock = pygame.time.Clock()
pygame.init()

window = pygame.display.set_mode((1, 1))
pygame.display.set_caption("Pacman")

screen = pygame.display.get_surface()

img_Background = pygame.image.load(os.path.join(SCRIPT_PATH,"res","backgrounds","1.gif")).convert()

snd_pellet = {}
snd_pellet[0] = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","pellet1.wav"))
snd_pellet[1] = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","pellet2.wav"))
snd_powerpellet = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","powerpellet.wav"))
snd_eatgh = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","eatgh2.wav"))
snd_fruitbounce = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","fruitbounce.wav"))
snd_eatfruit = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","eatfruit.wav"))
snd_extralife = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","extralife.wav"))

ghostcolor = {}
ghostcolor[0] = (255, 0, 0, 255)
ghostcolor[1] = (255, 128, 255, 255)
ghostcolor[2] = (128, 255, 255, 255)
ghostcolor[3] = (255, 128, 0, 255)
ghostcolor[4] = (50, 50, 255, 255) # blue, vulnerable ghost
ghostcolor[5] = (255, 255, 255, 255) # white, flashing ghost

#      ___________________
# ___/  class definitions  \_______________________________________________

class game ():

    def defaulthiscorelist(self):
            return [ (100000,"David") , (80000,"Andy") , (60000,"Count Pacula") , (40000,"Cleopacra") , (20000,"Brett Favre") , (10000,"Sergei Pachmaninoff") ]

    def gethiscores(self):
            """If res/hiscore.txt exists, read it. If not, return the default high scores.
               Output is [ (score,name) , (score,name) , .. ]. Always 6 entries."""
            try:
              f=open(os.path.join(SCRIPT_PATH,"res","hiscore.txt"))
              hs=[]
              for line in f:
                while len(line)>0 and (line[0]=="\n" or line[0]=="\r"): line=line[1:]
                while len(line)>0 and (line[-1]=="\n" or line[-1]=="\r"): line=line[:-1]
                score=int(line.split(" ")[0])
                name=line.partition(" ")[2]
                if score>99999999: score=99999999
                if len(name)>22: name=name[:22]
                hs.append((score,name))
              f.close()
              if len(hs)>6: hs=hs[:6]
              while len(hs)<6: hs.append((0,""))
              return hs
            except IOError:
              return self.defaulthiscorelist()
              
    def writehiscores(self,hs):
            """Given a new list, write it to the default file."""
            fname=os.path.join(SCRIPT_PATH,"res","hiscore.txt")
            f=open(fname,"w")
            for line in hs:
              f.write(str(line[0])+" "+line[1]+"\n")
            f.close()
            
    def getplayername(self):
            """Ask the player his name, to go on the high-score list."""
            if NO_WX: return USER_NAME
            try:
              import wx
            except:
              print("Pacman Error: No module wx. Can not ask the user his name!")
              print("     :(       Download wx from http://www.wxpython.org/")
              print("     :(       To avoid seeing this error again, set NO_WX in file pacman.pyw.")
              return USER_NAME
            app=wx.App(None)
            dlog=wx.TextEntryDialog(None,"You made the high-score list! Name:")
            dlog.ShowModal()
            name=dlog.GetValue()
            dlog.Destroy()
            app.Destroy()
            return name
              
    def updatehiscores(self,newscore):
            """Add newscore to the high score list, if appropriate."""
            hs=self.gethiscores()
            for line in hs:
              if newscore>=line[0]:
                hs.insert(hs.index(line),(newscore,self.getplayername()))
                hs.pop(-1)
                break
            self.writehiscores(hs)

    def makehiscorelist(self):
            "Read the High-Score file and convert it to a useable Surface."
            # My apologies for all the hard-coded constants.... -Andy
            f=pygame.font.Font(os.path.join(SCRIPT_PATH,"res","VeraMoBd.ttf"),10)
            scoresurf=pygame.Surface((276,86),pygame.SRCALPHA)
            scoresurf.set_alpha(200)
            linesurf=f.render(" "*18+"HIGH SCORES",1,(255,255,0))
            scoresurf.blit(linesurf,(0,0))
            hs=self.gethiscores()
            vpos=0
            for line in hs:
              vpos+=12
              linesurf=f.render(line[1].rjust(22)+str(line[0]).rjust(9),1,(255,255,255))
              scoresurf.blit(linesurf,(0,vpos))
            return scoresurf
            
    def drawmidgamehiscores(self):
            """Redraw the high-score list image after pacman dies."""
            self.imHiscores=self.makehiscorelist()

    def __init__ (self):
        self.levelNum = 0
        self.score = 0
        self.lives = 0
        
        # game "mode" variable
        # 1 = normal
        # 2 = hit ghost
        # 3 = game over
        # 4 = wait to start
        # 5 = wait after eating ghost
        # 6 = wait after finishing level
        self.mode = 0
        self.modeTimer = 0
        self.ghostTimer = 0
        self.ghostValue = 0
        self.fruitTimer = 0
        self.fruitScoreTimer = 0
        self.fruitScorePos = (0, 0)
        
        self.SetMode( 3 )
        
        # camera variables
        self.screenPixelPos = (0, 0) # absolute x,y position of the screen from the upper-left corner of the level
        self.screenNearestTilePos = (0, 0) # nearest-tile position of the screen from the UL corner
        self.screenPixelOffset = (0, 0) # offset in pixels of the screen from its nearest-tile position
        
        self.screenTileSize = (23, 21)
        self.screenSize = (self.screenTileSize[1] * 16, self.screenTileSize[0] * 16)

        # numerical display digits
        self.digit = {}
        for i in range(0, 10, 1):
            self.digit[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text",str(i) + ".gif")).convert()
        self.imLife = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text","life.gif")).convert()
        self.imGameOver = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text","gameover.gif")).convert()
        self.imReady = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text","ready.gif")).convert()
        self.imLogo = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text","logo.gif")).convert()
        self.imHiscores = self.makehiscorelist()
        
    def StartNewGame (self):
        self.levelNum = 1
        self.score = 0
        self.lives = 0
        
        self.SetMode( 1 )
        thisLevel.LoadLevel( thisGame.GetLevelNum() )
            
    def AddToScore (self, amount):
        
        extraLifeSet = [25000, 50000, 100000, 150000]
        
        for specialScore in extraLifeSet:
            if self.score < specialScore and self.score + amount >= specialScore:
                snd_extralife.play()
                # thisGame.lives += 1
        
        self.score += amount
        
    
    def DrawScore (self):
        self.DrawNumber (self.score, (24 + 16, self.screenSize[1] - 24) )
            
        for i in range(0, self.lives, 1):
            screen.blit (self.imLife, (24 + i * 10 + 16, self.screenSize[1] - 12) )
            
        screen.blit (thisFruit.imFruit[ thisFruit.fruitType ], (4 + 16, self.screenSize[1] - 20) )
            
        if self.mode == 3:
            screen.blit (self.imGameOver, (self.screenSize[0] / 2 - 32, self.screenSize[1] / 2 - 10) )
        elif self.mode == 4:
            screen.blit (self.imReady, (self.screenSize[0] / 2 - 20, self.screenSize[1] / 2 + 12) )
            
        self.DrawNumber (self.levelNum, (0, self.screenSize[1] - 12) )
            
    def DrawNumber (self, number, xxx_todo_changeme):
        (x, y) = xxx_todo_changeme
        strNumber = str(number)
        
        for i in range(0, len(str(number)), 1):
            if strNumber[i].isdigit():
                iDigit = float(strNumber[i])
                screen.blit (self.digit[ iDigit ], (x + i * 9, y) )
        
    def SmartMoveScreen (self):
            
        possibleScreenX = player.x - self.screenTileSize[1] / 2 * 16
        possibleScreenY = player.y - self.screenTileSize[0] / 2 * 16
        
        if possibleScreenX < 0:
            possibleScreenX = 0
        elif possibleScreenX > thisLevel.lvlWidth * 16 - self.screenSize[0]:
            possibleScreenX = thisLevel.lvlWidth * 16 - self.screenSize[0]
            
        if possibleScreenY < 0:
            possibleScreenY = 0
        elif possibleScreenY > thisLevel.lvlHeight * 16 - self.screenSize[1]:
            possibleScreenY = thisLevel.lvlHeight * 16 - self.screenSize[1]
        
        thisGame.MoveScreen( (possibleScreenX, possibleScreenY) )
        
    def MoveScreen (self, xxx_todo_changeme1 ):
        (newX, newY) = xxx_todo_changeme1
        self.screenPixelPos = (newX, newY)
        self.screenNearestTilePos = (int(newY / 16), int(newX / 16)) # nearest-tile position of the screen from the UL corner
        self.screenPixelOffset = (newX - self.screenNearestTilePos[1]*16, newY - self.screenNearestTilePos[0]*16)
        
    def GetScreenPos (self):
        return self.screenPixelPos
        
    def GetLevelNum (self):
        return self.levelNum
    
    def SetNextLevel (self):
        self.levelNum += 1
        
        self.SetMode( 4 )
        thisLevel.LoadLevel( thisGame.GetLevelNum() )
        
        player.velX = 0
        player.velY = 0
        player.anim_pacmanCurrent = player.anim_pacmanS
        
        
    def SetMode (self, newMode):
        self.mode = newMode
        self.modeTimer = 0
        # print " ***** GAME MODE IS NOW ***** " + str(newMode)
        
class node ():
    
    def __init__ (self):
        self.g = -1 # movement cost to move from previous node to this one (usually +10)
        self.h = -1 # estimated movement cost to move from this node to the ending node (remaining horizontal and vertical steps * 10)
        self.f = -1 # total movement cost of this node (= g + h)
        # parent node - used to trace path back to the starting node at the end
        self.parent = (-1, -1)
        # node type - 0 for empty space, 1 for wall (optionally, 2 for starting node and 3 for end)
        self.type = -1
        
class path_finder ():
    
    def __init__ (self):
        # map is a 1-DIMENSIONAL array.
        # use the Unfold( (row, col) ) function to convert a 2D coordinate pair
        # into a 1D index to use with this array.
        self.map = {}
        self.size = (-1, -1) # rows by columns
        
        self.pathChainRev = ""
        self.pathChain = ""
                
        # starting and ending nodes
        self.start = (-1, -1)
        self.end = (-1, -1)
        
        # current node (used by algorithm)
        self.current = (-1, -1)
        
        # open and closed lists of nodes to consider (used by algorithm)
        self.openList = []
        self.closedList = []
        
        # used in algorithm (adjacent neighbors path finder is allowed to consider)
        self.neighborSet = [ (0, -1), (0, 1), (-1, 0), (1, 0) ]
        
    def ResizeMap (self, xxx_todo_changeme2):
        (numRows, numCols) = xxx_todo_changeme2
        self.map = {}
        self.size = (numRows, numCols)

        # initialize path_finder map to a 2D array of empty nodes
        for row in range(0, self.size[0], 1):
            for col in range(0, self.size[1], 1):
                self.Set( (row, col), node() )
                self.SetType( (row, col), 0 )
        
    def CleanUpTemp (self):
        
        # this resets variables needed for a search (but preserves the same map / maze)
    
        self.pathChainRev = ""
        self.pathChain = ""
        self.current = (-1, -1)
        self.openList = []
        self.closedList = []
        
    def FindPath (self, startPos, endPos ):
        
        self.CleanUpTemp()
        
        # (row, col) tuples
        self.start = startPos
        self.end = endPos
        
        # add start node to open list
        self.AddToOpenList( self.start )
        self.SetG ( self.start, 0 )
        self.SetH ( self.start, 0 )
        self.SetF ( self.start, 0 )
        
        doContinue = True
        
        while (doContinue == True):
        
            thisLowestFNode = self.GetLowestFNode()

            if not thisLowestFNode == self.end and not thisLowestFNode == False:
                self.current = thisLowestFNode
                self.RemoveFromOpenList( self.current )
                self.AddToClosedList( self.current )
                
                for offset in self.neighborSet:
                    thisNeighbor = (self.current[0] + offset[0], self.current[1] + offset[1])
                    
                    if not thisNeighbor[0] < 0 and not thisNeighbor[1] < 0 and not thisNeighbor[0] > self.size[0] - 1 and not thisNeighbor[1] > self.size[1] - 1 and not self.GetType( thisNeighbor ) == 1:
                        cost = self.GetG( self.current ) + 10
                        
                        if self.IsInOpenList( thisNeighbor ) and cost < self.GetG( thisNeighbor ):
                            self.RemoveFromOpenList( thisNeighbor )
                            
                        #if self.IsInClosedList( thisNeighbor ) and cost < self.GetG( thisNeighbor ):
                        #   self.RemoveFromClosedList( thisNeighbor )
                            
                        if not self.IsInOpenList( thisNeighbor ) and not self.IsInClosedList( thisNeighbor ):
                            self.AddToOpenList( thisNeighbor )
                            self.SetG( thisNeighbor, cost )
                            self.CalcH( thisNeighbor )
                            self.CalcF( thisNeighbor )
                            self.SetParent( thisNeighbor, self.current )
            else:
                doContinue = False
                        
        if thisLowestFNode == False:
            return False
                        
        # reconstruct path
        self.current = self.end
        while not self.current == self.start:
            # build a string representation of the path using R, L, D, U
            if self.current[1] > self.GetParent(self.current)[1]:
                self.pathChainRev += 'R' 
            elif self.current[1] < self.GetParent(self.current)[1]:
                self.pathChainRev += 'L'
            elif self.current[0] > self.GetParent(self.current)[0]:
                self.pathChainRev += 'D'
            elif self.current[0] < self.GetParent(self.current)[0]:
                self.pathChainRev += 'U'
            self.current = self.GetParent(self.current)
            self.SetType( self.current, 4)
            
        # because pathChainRev was constructed in reverse order, it needs to be reversed!
        for i in range(len(self.pathChainRev) - 1, -1, -1):
            self.pathChain += self.pathChainRev[i]
        
        # set start and ending positions for future reference
        self.SetType( self.start, 2)
        self.SetType( self.end, 3)
        
        return self.pathChain

    def Unfold (self, xxx_todo_changeme3):
        # this function converts a 2D array coordinate pair (row, col)
        # to a 1D-array index, for the object's 1D map array.
        (row, col) = xxx_todo_changeme3
        return (row * self.size[1]) + col
    
    def Set (self, xxx_todo_changeme4, newNode):
        # sets the value of a particular map cell (usually refers to a node object)
        (row, col) = xxx_todo_changeme4
        self.map[ self.Unfold((row, col)) ] = newNode
        
    def GetType (self, xxx_todo_changeme5):
        (row, col) = xxx_todo_changeme5
        return self.map[ self.Unfold((row, col)) ].type
        
    def SetType (self, xxx_todo_changeme6, newValue):
        (row, col) = xxx_todo_changeme6
        self.map[ self.Unfold((row, col)) ].type = newValue

    def GetF (self, xxx_todo_changeme7):
        (row, col) = xxx_todo_changeme7
        return self.map[ self.Unfold((row, col)) ].f

    def GetG (self, xxx_todo_changeme8):
        (row, col) = xxx_todo_changeme8
        return self.map[ self.Unfold((row, col)) ].g
    
    def GetH (self, xxx_todo_changeme9):
        (row, col) = xxx_todo_changeme9
        return self.map[ self.Unfold((row, col)) ].h
        
    def SetG (self, xxx_todo_changeme10, newValue ):
        (row, col) = xxx_todo_changeme10
        self.map[ self.Unfold((row, col)) ].g = newValue

    def SetH (self, xxx_todo_changeme11, newValue ):
        (row, col) = xxx_todo_changeme11
        self.map[ self.Unfold((row, col)) ].h = newValue
        
    def SetF (self, xxx_todo_changeme12, newValue ):
        (row, col) = xxx_todo_changeme12
        self.map[ self.Unfold((row, col)) ].f = newValue
        
    def CalcH (self, xxx_todo_changeme13):
        (row, col) = xxx_todo_changeme13
        self.map[ self.Unfold((row, col)) ].h = abs(row - self.end[0]) + abs(col - self.end[0])
        
    def CalcF (self, xxx_todo_changeme14):
        (row, col) = xxx_todo_changeme14
        unfoldIndex = self.Unfold((row, col))
        self.map[unfoldIndex].f = self.map[unfoldIndex].g + self.map[unfoldIndex].h
    
    def AddToOpenList (self, xxx_todo_changeme15 ):
        (row, col) = xxx_todo_changeme15
        self.openList.append( (row, col) )
        
    def RemoveFromOpenList (self, xxx_todo_changeme16 ):
        (row, col) = xxx_todo_changeme16
        self.openList.remove( (row, col) )
        
    def IsInOpenList (self, xxx_todo_changeme17 ):
        (row, col) = xxx_todo_changeme17
        if self.openList.count( (row, col) ) > 0:
            return True
        else:
            return False
        
    def GetLowestFNode (self):
        lowestValue = 1000 # start arbitrarily high
        lowestPair = (-1, -1)
        
        for iOrderedPair in self.openList:
            if self.GetF( iOrderedPair ) < lowestValue:
                lowestValue = self.GetF( iOrderedPair )
                lowestPair = iOrderedPair
        
        if not lowestPair == (-1, -1):
            return lowestPair
        else:
            return False
        
    def AddToClosedList (self, xxx_todo_changeme18 ):
        (row, col) = xxx_todo_changeme18
        self.closedList.append( (row, col) )
        
    def IsInClosedList (self, xxx_todo_changeme19 ):
        (row, col) = xxx_todo_changeme19
        if self.closedList.count( (row, col) ) > 0:
            return True
        else:
            return False

    def SetParent (self, xxx_todo_changeme20, xxx_todo_changeme21 ):
        (row, col) = xxx_todo_changeme20
        (parentRow, parentCol) = xxx_todo_changeme21
        self.map[ self.Unfold((row, col)) ].parent = (parentRow, parentCol)

    def GetParent (self, xxx_todo_changeme22 ):
        (row, col) = xxx_todo_changeme22
        return self.map[ self.Unfold((row, col)) ].parent
        
    def draw (self):
        for row in range(0, self.size[0], 1):
            for col in range(0, self.size[1], 1):
            
                thisTile = self.GetType((row, col))
                screen.blit (tileIDImage[ thisTile ], (col * 32, row * 32))
        
class ghost ():
    def __init__ (self, ghostID):
        self.x = 0
        self.y = 0
        self.velX = 0
        self.velY = 0
        self.speed = 1 * speedMultiplier
        
        self.nearestRow = 0
        self.nearestCol = 0
        
        self.id = ghostID
        
        # ghost "state" variable
        # 1 = normal
        # 2 = vulnerable
        # 3 = spectacles
        self.state = 1
        
        self.homeX = 0
        self.homeY = 0
        
        self.currentPath = ""
        
        self.anim = {}
        for i in range(1, 7, 1):
            self.anim[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","ghost " + str(i) + ".gif")).convert()
            
            # change the ghost color in this frame
            for y in range(0, 16, 1):
                for x in range(0, 16, 1):
                
                    if self.anim[i].get_at( (x, y) ) == (255, 0, 0, 255):
                        # default, red ghost body color
                        self.anim[i].set_at( (x, y), ghostcolor[ self.id ] )
            
        self.animFrame = 1
        self.animDelay = 0
        
    def Draw (self):
        
        if thisGame.mode == 3:
            return False
        
        
        # ghost eyes --
        for y in range(4, 8, 1):
            for x in range(3, 7, 1):
                self.anim[ self.animFrame ].set_at( (x, y), (255, 255, 255, 255) )  
                self.anim[ self.animFrame ].set_at( (x+6, y), (255, 255, 255, 255) )
                
                if player.x > self.x and player.y > self.y:
                    #player is to lower-right
                    pupilSet = (5, 6)
                elif player.x < self.x and player.y > self.y:
                    #player is to lower-left
                    pupilSet = (3, 6)
                elif player.x > self.x and player.y < self.y:
                    #player is to upper-right
                    pupilSet = (5, 4)
                elif player.x < self.x and player.y < self.y:
                    #player is to upper-left
                    pupilSet = (3, 4)
                else:
                    pupilSet = (4, 6)
                    
        for y in range(pupilSet[1], pupilSet[1] + 2, 1):
            for x in range(pupilSet[0], pupilSet[0] + 2, 1):
                self.anim[ self.animFrame ].set_at( (x, y), (0, 0, 255, 255) )  
                self.anim[ self.animFrame ].set_at( (x+6, y), (0, 0, 255, 255) )    
        # -- end ghost eyes
        
        if self.state == 1:
            # draw regular ghost (this one)
            screen.blit (self.anim[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
        elif self.state == 2:
            # draw vulnerable ghost
            
            if thisGame.ghostTimer > 100:
                # blue
                screen.blit (ghosts[4].anim[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
            else:
                # blue/white flashing
                tempTimerI = int(thisGame.ghostTimer / 10)
                if tempTimerI == 1 or tempTimerI == 3 or tempTimerI == 5 or tempTimerI == 7 or tempTimerI == 9:
                    screen.blit (ghosts[5].anim[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
                else:
                    screen.blit (ghosts[4].anim[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
            
        elif self.state == 3:
            # draw glasses
            screen.blit (tileIDImage[ tileID[ 'glasses' ] ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
        
        if thisGame.mode == 6 or thisGame.mode == 7:
            # don't animate ghost if the level is complete
            return False
        
        self.animDelay += 1
        
        if self.animDelay == 2:
            self.animFrame += 1 
        
            if self.animFrame == 7:
                # wrap to beginning
                self.animFrame = 1
                
            self.animDelay = 0
            
    def Move (self):
        

        self.x += self.velX
        self.y += self.velY
        
        self.nearestRow = int(((self.y + 8) / 16))
        self.nearestCol = int(((self.x + 8) / 16))

        if (self.x % 16) == 0 and (self.y % 16) == 0:
            # if the ghost is lined up with the grid again
            # meaning, it's time to go to the next path item
            
            if (self.currentPath):
                self.currentPath = self.currentPath[1:]
                self.FollowNextPathWay()
        
            else:
                self.x = self.nearestCol * 16
                self.y = self.nearestRow * 16
            
                # chase pac-man
                self.currentPath = path.FindPath( (self.nearestRow, self.nearestCol), (player.nearestRow, player.nearestCol) )
                self.FollowNextPathWay()
        
        if (self.nearestCol > thisLevel.getWidth()) or (self.nearestRow > thisLevel.getHeight()) or (self.nearestCol < 0) or (self.nearestRow < 0):
            self.x = self.homeX
            self.y = self.homeY

    def generatePathway(self):
        if not self.state == 3:
            # chase pac-man
            self.currentPath = path.FindPath( (self.nearestRow, self.nearestCol), (player.nearestRow, player.nearestCol) )
        else:
            # glasses found way back to ghost box
            self.state = 1
            self.speed = self.speed / 4
            
            # give ghost a path to a random spot (containing a pellet)
            (randRow, randCol) = (0, 0)

            while not thisLevel.GetMapTile((randRow, randCol)) == tileID[ 'pellet' ] or (randRow, randCol) == (0, 0):
                randRow = random.randint(1, thisLevel.lvlHeight - 2)
                randCol = random.randint(1, thisLevel.lvlWidth - 2)

            self.currentPath = path.FindPath( (self.nearestRow, self.nearestCol), (randRow, randCol) )

    def FollowPath(self):
        if self.currentPath:
            if self.currentPath[0] == "L":
                (self.velX, self.velY) = (-self.speed, 0)
            elif self.currentPath[0] == "R":
                (self.velX, self.velY) = (self.speed, 0)
            elif  self.currentPath[0] == "U":
                (self.velX, self.velY) = (0, -self.speed)
            elif  self.currentPath[0] == "D":
                (self.velX, self.velY) = (0, self.speed)
        else:
            # print("End of pathing for ghost: ", self.id)
            self.velX = 0
            self.velY = 0
            self.generatePathway()
            
    def FollowNextPathWay (self):
        
        # print "Ghost " + str(self.id) + " rem: " + self.currentPath
        
        # only follow this pathway if there is a possible path found!
        if not self.currentPath == False:
        
            if self.currentPath:
               self.FollowPath()
                    
            else:
                # print("Gen path for ghost: ", self.id)
                # this ghost has reached his destination!!
                
                self.generatePathway()
                self.FollowPath()

class fruit ():
    def __init__ (self):
        # when fruit is not in use, it's in the (-1, -1) position off-screen.
        self.slowTimer = 0
        self.x = -16
        self.y = -16
        self.velX = 0
        self.velY = 0
        self.speed = 1 * speedMultiplier
        self.active = False
        
        self.bouncei = 0
        self.bounceY = 0
        
        self.nearestRow = (-1, -1)
        self.nearestCol = (-1, -1)
        
        self.imFruit = {}
        for i in range(0, 5, 1):
            self.imFruit[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","fruit " + str(i) + ".gif")).convert()
        
        self.currentPath = ""
        self.fruitType = 1
        
    def Draw (self):
        
        if thisGame.mode == 3 or self.active == False:
            return False
        
        screen.blit (self.imFruit[ self.fruitType ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1] - self.bounceY))

            
    def Move (self):
        
        if self.active == False:
            return False
        
        self.bouncei += 1
        if self.bouncei == 1:
            self.bounceY = 2
        elif self.bouncei == 2:
            self.bounceY = 4
        elif self.bouncei == 3:
            self.bounceY = 5
        elif self.bouncei == 4:
            self.bounceY = 5
        elif self.bouncei == 5:
            self.bounceY = 6
        elif self.bouncei == 6:
            self.bounceY = 6
        elif self.bouncei == 9:
            self.bounceY = 6
        elif self.bouncei == 10:
            self.bounceY = 5
        elif self.bouncei == 11:
            self.bounceY = 5
        elif self.bouncei == 12:
            self.bounceY = 4
        elif self.bouncei == 13:
            self.bounceY = 3
        elif self.bouncei == 14:
            self.bounceY = 2
        elif self.bouncei == 15:
            self.bounceY = 1
        elif self.bouncei == 16:
            self.bounceY = 0
            self.bouncei = 0
            snd_fruitbounce.play()
        
        self.slowTimer += 1
        if self.slowTimer == 2:
            self.slowTimer = 0
            
            self.x += self.velX
            self.y += self.velY
            
            self.nearestRow = int(((self.y + 8) / 16))
            self.nearestCol = int(((self.x + 8) / 16))

            if (self.x % 16) == 0 and (self.y % 16) == 0:
                # if the fruit is lined up with the grid again
                # meaning, it's time to go to the next path item
                
                if len(self.currentPath) > 0:
                    self.currentPath = self.currentPath[1:]
                    self.FollowNextPathWay()
            
                else:
                    self.x = self.nearestCol * 16
                    self.y = self.nearestRow * 16
                    
                    self.active = False
                    thisGame.fruitTimer = 0
            
    def FollowNextPathWay (self):
        

        # only follow this pathway if there is a possible path found!
        if not self.currentPath == False:
            try:
                if self.currentPath:
                    if self.currentPath[0] == "L":
                        (self.velX, self.velY) = (-self.speed, 0)
                    elif self.currentPath[0] == "R":
                        (self.velX, self.velY) = (self.speed, 0)
                    elif self.currentPath[0] == "U":
                        (self.velX, self.velY) = (0, -self.speed)
                    elif self.currentPath[0] == "D":
                        (self.velX, self.velY) = (0, self.speed)
            except IndexError:
                print(self.currentPath)

class pacman ():
    
    def __init__ (self):
        self.x = 0
        self.y = 0
        self.velX = 0
        self.velY = 0
        self.speed = 2 * speedMultiplier

        self.reward = 0
        
        self.nearestRow = 0
        self.nearestCol = 0
        
        self.homeX = 0
        self.homeY = 0
        
        self.anim_pacmanL = {}
        self.anim_pacmanR = {}
        self.anim_pacmanU = {}
        self.anim_pacmanD = {}
        self.anim_pacmanS = {}
        self.anim_pacmanCurrent = {}
        
        for i in range(1, 9, 1):
            self.anim_pacmanL[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman-l " + str(i) + ".gif")).convert()
            self.anim_pacmanR[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman-r " + str(i) + ".gif")).convert()
            self.anim_pacmanU[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman-u " + str(i) + ".gif")).convert()
            self.anim_pacmanD[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman-d " + str(i) + ".gif")).convert()
            self.anim_pacmanS[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman.gif")).convert()

        self.pelletSndNum = 0

    def map(self):
        walls = np.zeros((thisLevel.getHeight(), thisLevel.getWidth()))
        pacmanLoc = np.zeros((thisLevel.getHeight(), thisLevel.getWidth()))
        dots = np.zeros((thisLevel.getHeight(), thisLevel.getWidth()))
        capsules = np.zeros((thisLevel.getHeight(), thisLevel.getWidth()))
        ghostLoc = np.zeros((thisLevel.getHeight(), thisLevel.getWidth()))
        blueGhostLoc = np.zeros((thisLevel.getHeight(), thisLevel.getWidth()))

        for x in range(thisLevel.getWidth()):
            for y in range(thisLevel.getHeight()):
                if thisLevel.IsWall((y, x), True):
                    walls[y, x] = 1
                elif thisLevel.TileHasPellet((y, x)):
                    dots[y, x] = 1
                elif thisLevel.TileHasCapsule((y, x)):
                    capsules[y, x] = 1
        
        for i in range(4):
            ghostRow = ghosts[i].nearestRow
            ghostCol = ghosts[i].nearestCol
            if ghosts[i].state == 1:
                ghostLoc[ghostRow, ghostCol] = 1
            elif ghosts[i].state == 2:
                blueGhostLoc[ghostRow, ghostCol] = 1
        
        return np.float32(np.array([walls, pacmanLoc, dots, capsules, ghostLoc, blueGhostLoc]))
        
    def Move (self):
        dead = False
        
        self.nearestRow = int(((self.y + 8) / 16))
        self.nearestCol = int(((self.x + 8) / 16))

        self.reward = time

        # make sure the current velocity will not cause a collision before moving
        if not thisLevel.CheckIfHitWall((self.x + self.velX, self.y + self.velY), (self.nearestRow, self.nearestCol)):
            # it's ok to Move
            self.x += self.velX
            self.y += self.velY
            
            # check for collisions with other tiles (pellets, etc)
            thisLevel.CheckIfHitSomething((self.x, self.y), (self.nearestRow, self.nearestCol))
            
            # check for collisions with the ghosts
            for i in range(0, 4, 1):
                if thisLevel.CheckIfHit( (self.x, self.y), (ghosts[i].x, ghosts[i].y), 16):
                    # hit a ghost
                    
                    if ghosts[i].state == 1:
                        # ghost is normal
                        thisGame.SetMode( 2 )
                        dead = True
                        self.reward = lose
                        
                    elif ghosts[i].state == 2:
                        # ghost is vulnerable
                        # give them glasses
                        # make them run
                        thisGame.AddToScore(thisGame.ghostValue)
                        thisGame.ghostValue = thisGame.ghostValue * 2
                        snd_eatgh.play()

                        self.reward = eatGhost
                        
                        ghosts[i].state = 3
                        ghosts[i].speed = ghosts[i].speed * 4
                        # and send them to the ghost box
                        ghosts[i].x = ghosts[i].nearestCol * 16
                        ghosts[i].y = ghosts[i].nearestRow * 16
                        ghosts[i].currentPath = path.FindPath( (ghosts[i].nearestRow, ghosts[i].nearestCol), (thisLevel.GetGhostBoxPos()[0]+1, thisLevel.GetGhostBoxPos()[1]) )
                        ghosts[i].FollowNextPathWay()
                        
                        # set game mode to brief pause after eating
                        # thisGame.SetMode( 5 )
                        
            # check for collisions with the fruit
            if thisFruit.active == True:
                if thisLevel.CheckIfHit( (self.x, self.y), (thisFruit.x, thisFruit.y), 8):
                    thisGame.AddToScore(2500)
                    thisFruit.active = False
                    thisGame.fruitTimer = 0
                    thisGame.fruitScoreTimer = 120
                    snd_eatfruit.play()
        
        else:
            # we're going to hit a wall -- stop moving
            self.velX = 0
            self.velY = 0
            
        # deal with power-pellet ghost timer
        if thisGame.ghostTimer > 0:
            thisGame.ghostTimer -= (1 * speedMultiplier) 
            
            if thisGame.ghostTimer <= 0:
                for i in range(0, 4, 1):
                    if ghosts[i].state == 2:
                        ghosts[i].state = 1
                self.ghostValue = 0
                
        # deal with fruit timer
        thisGame.fruitTimer += 1
        if thisGame.fruitTimer == 500:
            pathwayPair = thisLevel.GetPathwayPairPos()
            
            if not pathwayPair == False:
            
                pathwayEntrance = pathwayPair[0]
                pathwayExit = pathwayPair[1]
                
                thisFruit.active = True
                
                thisFruit.nearestRow = pathwayEntrance[0]
                thisFruit.nearestCol = pathwayEntrance[1]
                
                thisFruit.x = thisFruit.nearestCol * 16
                thisFruit.y = thisFruit.nearestRow * 16
                
                thisFruit.currentPath = path.FindPath( (thisFruit.nearestRow, thisFruit.nearestCol), pathwayExit )
                thisFruit.FollowNextPathWay()
            
        if thisGame.fruitScoreTimer > 0:
            thisGame.fruitScoreTimer -= 1

        return self.map(), self.reward, dead
            
        
    def Draw (self):
        
        if thisGame.mode == 3:
            return False
        
        # set the current frame array to match the direction pacman is facing
        if self.velX > 0:
            self.anim_pacmanCurrent = self.anim_pacmanR
        elif self.velX < 0:
            self.anim_pacmanCurrent = self.anim_pacmanL
        elif self.velY > 0:
            self.anim_pacmanCurrent = self.anim_pacmanD
        elif self.velY < 0:
            self.anim_pacmanCurrent = self.anim_pacmanU
            
        screen.blit (self.anim_pacmanCurrent[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
        
        if thisGame.mode == 1:
            if not self.velX == 0 or not self.velY == 0:
                # only Move mouth when pacman is moving
                self.animFrame += 1 
            
            if self.animFrame == 9:
                # wrap to beginning
                self.animFrame = 1
            
class level ():
    
    def __init__ (self):
        self.lvlWidth = 0
        self.lvlHeight = 0
        self.edgeLightColor = (255, 255, 0, 255)
        self.edgeShadowColor = (255, 150, 0, 255)
        self.fillColor = (0, 255, 255, 255)
        self.pelletColor = (255, 255, 255, 255)
        
        self.map = {}
        
        self.pellets = 0
        self.powerPelletBlinkTimer = 0

    def getWidth(self):
        return self.lvlWidth
    
    def getHeight(self):
        return self.lvlHeight
        
    def SetMapTile (self, xxx_todo_changeme23, newValue):
        (row, col) = xxx_todo_changeme23
        self.map[ (row * self.lvlWidth) + col ] = newValue
        
    def GetMapTile (self, xxx_todo_changeme24):
        (row, col) = xxx_todo_changeme24
        if row >= 0 and row < self.lvlHeight and col >= 0 and col < self.lvlWidth:
            return self.map[ (row * self.lvlWidth) + col ]
        else:
            return 0
    
    def IsWall (self, xxx_todo_changeme25, hitGhostWall):
    
        (row, col) = xxx_todo_changeme25
        if row > thisLevel.lvlHeight - 1 or row < 0:
            return True
        
        if col > thisLevel.lvlWidth - 1 or col < 0:
            return True
    
        # check the offending tile ID
        result = thisLevel.GetMapTile((row, col))
        
        # if the tile was a wall
        if (result >= 100 and result <= 199) or (hitGhostWall == True and result == tileID[ 'ghost-door' ]):
            return True
        else:
            return False
    
                    
    def CheckIfHitWall (self, xxx_todo_changeme26, xxx_todo_changeme27):
    
        (possiblePlayerX, possiblePlayerY) = xxx_todo_changeme26
        (row, col) = xxx_todo_changeme27
        numCollisions = 0
        
        # check each of the 9 surrounding tiles for a collision
        for iRow in range(row - 1, row + 2, 1):
            for iCol in range(col - 1, col + 2, 1):
            
                if  (possiblePlayerX - (iCol * 16) < 16) and (possiblePlayerX - (iCol * 16) > -16) and (possiblePlayerY - (iRow * 16) < 16) and (possiblePlayerY - (iRow * 16) > -16):
                    
                    if self.IsWall((iRow, iCol), True):
                        numCollisions += 1
                        
        if numCollisions > 0:
            return True
        else:
            return False
        
        
    def CheckIfHit (self, xxx_todo_changeme28, xxx_todo_changeme29, cushion):
    
        (playerX, playerY) = xxx_todo_changeme28
        (x, y) = xxx_todo_changeme29
        if (playerX - x < cushion) and (playerX - x > -cushion) and (playerY - y < cushion) and (playerY - y > -cushion):
            return True
        else:
            return False

    def TileHasPellet (self, xxx_todo_changeme31):
        (row, col) = xxx_todo_changeme31
        
        # check the offending tile ID
        result = thisLevel.GetMapTile((row, col))

        if (result == tileID[ 'pellet' ]):
            return True

        return False

    def TileHasCapsule(self, xxx_todo_changeme31):
        (row, col) = xxx_todo_changeme31
        
        # check the offending tile ID
        result = thisLevel.GetMapTile((row, col))

        if (result == tileID[ 'pellet-power' ]):
            return True

        return False

    def CheckIfHitSomething (self, xxx_todo_changeme30, xxx_todo_changeme31):
    
        (playerX, playerY) = xxx_todo_changeme30
        (row, col) = xxx_todo_changeme31
        for iRow in range(row - 1, row + 2, 1):
            for iCol in range(col - 1, col + 2, 1):
            
                if  (playerX - (iCol * 16) < 16) and (playerX - (iCol * 16) > -16) and (playerY - (iRow * 16) < 16) and (playerY - (iRow * 16) > -16):
                    # check the offending tile ID
                    result = thisLevel.GetMapTile((iRow, iCol))
        
                    if result == tileID[ 'pellet' ]:
                        # got a pellet
                        thisLevel.SetMapTile((iRow, iCol), 0)
                        snd_pellet[player.pelletSndNum].play()
                        player.pelletSndNum = 1 - player.pelletSndNum
                        player.reward = eatDot
                        
                        thisLevel.pellets -= 1
                        
                        thisGame.AddToScore(10)
                        
                        if thisLevel.pellets == 0:
                            # no more pellets left!
                            # WON THE LEVEL
                            thisGame.SetMode( 6 )
                            
                        
                    elif result == tileID[ 'pellet-power' ]:
                        # got a power pellet
                        thisLevel.SetMapTile((iRow, iCol), 0)
                        snd_powerpellet.play()
                        player.reward = eatDot
                        
                        thisGame.AddToScore(100)
                        thisGame.ghostValue = 200
                        
                        thisGame.ghostTimer = 360
                        for i in range(0, 4, 1):
                            if ghosts[i].state == 1:
                                ghosts[i].state = 2
                        
                    elif result == tileID[ 'door-h' ]:
                        # ran into a horizontal door
                        for i in range(0, thisLevel.lvlWidth, 1):
                            if not i == iCol:
                                if thisLevel.GetMapTile((iRow, i)) == tileID[ 'door-h' ]:
                                    player.x = i * 16
                                    
                                    if player.velX > 0:
                                        player.x += 16
                                    else:
                                        player.x -= 16
                                        
                    elif result == tileID[ 'door-v' ]:
                        # ran into a vertical door
                        for i in range(0, thisLevel.lvlHeight, 1):
                            if not i == iRow:
                                if thisLevel.GetMapTile((i, iCol)) == tileID[ 'door-v' ]:
                                    player.y = i * 16
                                    
                                    if player.velY > 0:
                                        player.y += 16
                                    else:
                                        player.y -= 16
                                        
    def GetGhostBoxPos (self):
        
        for row in range(0, self.lvlHeight, 1):
            for col in range(0, self.lvlWidth, 1):
                if self.GetMapTile((row, col)) == tileID[ 'ghost-door' ]:
                    return (row, col)
                
        return False
    
    def GetPathwayPairPos (self):
        
        doorArray = []
        
        for row in range(0, self.lvlHeight, 1):
            for col in range(0, self.lvlWidth, 1):
                if self.GetMapTile((row, col)) == tileID[ 'door-h' ]:
                    # found a horizontal door
                    doorArray.append( (row, col) )
                elif self.GetMapTile((row, col)) == tileID[ 'door-v' ]:
                    # found a vertical door
                    doorArray.append( (row, col) )
        
        if len(doorArray) == 0:
            return False
        
        chosenDoor = random.randint(0, len(doorArray) - 1)
        
        if self.GetMapTile( doorArray[chosenDoor] ) == tileID[ 'door-h' ]:
            # horizontal door was chosen
            # look for the opposite one
            for i in range(0, thisLevel.lvlWidth, 1):
                if not i == doorArray[chosenDoor][1]:
                    if thisLevel.GetMapTile((doorArray[chosenDoor][0], i)) == tileID[ 'door-h' ]:
                        return doorArray[chosenDoor], (doorArray[chosenDoor][0], i)
        else:
            # vertical door was chosen
            # look for the opposite one
            for i in range(0, thisLevel.lvlHeight, 1):
                if not i == doorArray[chosenDoor][0]:
                    if thisLevel.GetMapTile((i, doorArray[chosenDoor][1])) == tileID[ 'door-v' ]:
                        return doorArray[chosenDoor], (i, doorArray[chosenDoor][1])
                    
        return False
        
    def PrintMap (self):
        
        for row in range(0, self.lvlHeight, 1):
            outputLine = ""
            for col in range(0, self.lvlWidth, 1):
            
                outputLine += str( self.GetMapTile((row, col)) ) + ", "
                
            # print outputLine
            
    def DrawMap (self):
        
        self.powerPelletBlinkTimer = 1
        # if self.powerPelletBlinkTimer == 60:
        #     self.powerPelletBlinkTimer = 0
        
        for row in range(-1, thisGame.screenTileSize[0] +1, 1):
            outputLine = ""
            for col in range(-1, thisGame.screenTileSize[1] +1, 1):

                # row containing tile that actually goes here
                actualRow = thisGame.screenNearestTilePos[0] + row
                actualCol = thisGame.screenNearestTilePos[1] + col

                useTile = self.GetMapTile((actualRow, actualCol))
                if not useTile == 0 and not useTile == tileID['door-h'] and not useTile == tileID['door-v']:
                    # if this isn't a blank tile

                    if useTile == tileID['pellet-power']:
                        if self.powerPelletBlinkTimer < 30:
                            screen.blit (tileIDImage[ useTile ], (col * 16 - thisGame.screenPixelOffset[0], row * 16 - thisGame.screenPixelOffset[1]) )

                    elif useTile == tileID['showlogo']:
                        screen.blit (thisGame.imLogo, (col * 16 - thisGame.screenPixelOffset[0], row * 16 - thisGame.screenPixelOffset[1]) )
                    
                    elif useTile == tileID['hiscores']:
                            screen.blit(thisGame.imHiscores,(col*16-thisGame.screenPixelOffset[0],row*16-thisGame.screenPixelOffset[1]))
                    
                    else:
                        screen.blit (tileIDImage[ useTile ], (col * 16 - thisGame.screenPixelOffset[0], row * 16 - thisGame.screenPixelOffset[1]) )
        
    def LoadLevel (self, levelNum):
        
        self.map = {}
        
        self.pellets = 0
        
        f = open(os.path.join(SCRIPT_PATH,"res","levels",str(levelNum) + ".txt"), 'r')
        # ANDY -- edit this
        #fileOutput = f.read()
        #str_splitByLine = fileOutput.split('\n')
        lineNum=-1
        rowNum = 0
        useLine = False
        isReadingLevelData = False
          
        for line in f:

          lineNum += 1
        
            # print " ------- Level Line " + str(lineNum) + " -------- "
          while len(line)>0 and (line[-1]=="\n" or line[-1]=="\r"): line=line[:-1]
          while len(line)>0 and (line[0]=="\n" or line[0]=="\r"): line=line[1:]
          str_splitBySpace = line.split(' ')
            
            
          j = str_splitBySpace[0]
                
          if (j == "'" or j == ""):
                # comment / whitespace line
                # print " ignoring comment line.. "
                useLine = False
          elif j == "#":
                # special divider / attribute line
                useLine = False
                
                firstWord = str_splitBySpace[1]
                
                if firstWord == "lvlwidth":
                    self.lvlWidth = int( str_splitBySpace[2] )
                    # print "Width is " + str( self.lvlWidth )
                    
                elif firstWord == "lvlheight":
                    self.lvlHeight = int( str_splitBySpace[2] )
                    # print "Height is " + str( self.lvlHeight )
                    
                elif firstWord == "edgecolor":
                    # edge color keyword for backwards compatibility (single edge color) mazes
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.edgeLightColor = (red, green, blue, 255)
                    self.edgeShadowColor = (red, green, blue, 255)
                    
                elif firstWord == "edgelightcolor":
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.edgeLightColor = (red, green, blue, 255)
                    
                elif firstWord == "edgeshadowcolor":
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.edgeShadowColor = (red, green, blue, 255)
                
                elif firstWord == "fillcolor":
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.fillColor = (red, green, blue, 255)
                    
                elif firstWord == "pelletcolor":
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.pelletColor = (red, green, blue, 255)
                    
                elif firstWord == "fruittype":
                    thisFruit.fruitType = int( str_splitBySpace[2] )
                    
                elif firstWord == "startleveldata":
                    isReadingLevelData = True
                        # print "Level data has begun"
                    rowNum = 0
                    
                elif firstWord == "endleveldata":
                    isReadingLevelData = False
                    # print "Level data has ended"
                    
          else:
                useLine = True
                
                
            # this is a map data line   
          if useLine == True:
                
                if isReadingLevelData == True:
                        
                    # print str( len(str_splitBySpace) ) + " tiles in this column"
                    
                    for k in range(0, self.lvlWidth, 1):
                        self.SetMapTile((rowNum, k), int(str_splitBySpace[k]) )
                        
                        thisID = int(str_splitBySpace[k])
                        if thisID == 4: 
                            # starting position for pac-man
                            
                            player.homeX = k * 16
                            player.homeY = rowNum * 16
                            self.SetMapTile((rowNum, k), 0 )
                            
                        elif thisID >= 10 and thisID <= 13:
                            # one of the ghosts
                            
                            ghosts[thisID - 10].homeX = k * 16
                            ghosts[thisID - 10].homeY = rowNum * 16
                            self.SetMapTile((rowNum, k), 0 )
                        
                        elif thisID == 2:
                            # pellet
                            
                            self.pellets += 1
                            
                    rowNum += 1
                    
                
        # reload all tiles and set appropriate colors
        GetCrossRef()

        # load map into the pathfinder object
        path.ResizeMap( (self.lvlHeight, self.lvlWidth) )
        
        for row in range(0, path.size[0], 1):
            for col in range(0, path.size[1], 1):
                if self.IsWall( (row, col), False ):
                    path.SetType( (row, col), 1 )
                else:
                    path.SetType( (row, col), 0 )
        
        # do all the level-starting stuff
        self.Restart()
        
    def Restart (self):
        
        for i in range(0, 4, 1):
            # move ghosts back to home

            ghosts[i].x = ghosts[i].homeX
            ghosts[i].y = ghosts[i].homeY
            ghosts[i].velX = 0
            ghosts[i].velY = 0
            ghosts[i].state = 1
            ghosts[i].speed = 1 * speedMultiplier
            ghosts[i].Move()
            
            # give each ghost a path to a random spot (containing a pellet)
            (randRow, randCol) = (0, 0)

            while not self.GetMapTile((randRow, randCol)) == tileID[ 'pellet' ] or (randRow, randCol) == (0, 0):
                randRow = random.randint(1, self.lvlHeight - 2)
                randCol = random.randint(1, self.lvlWidth - 2)
            
            # print "Ghost " + str(i) + " headed towards " + str((randRow, randCol))
            ghosts[i].currentPath = path.FindPath( (ghosts[i].nearestRow, ghosts[i].nearestCol), (randRow, randCol) )
            ghosts[i].FollowNextPathWay()
            
        thisFruit.active = False
            
        thisGame.fruitTimer = 0

        player.x = player.homeX
        player.y = player.homeY
        player.velX = 0
        player.velY = 0
        
        player.anim_pacmanCurrent = player.anim_pacmanS
        player.animFrame = 3


def CheckIfCloseButton(events):
    for event in events: 
        if event.type == QUIT: 
            sys.exit(0)


def CheckInputs(action): 
    if thisGame.mode == 1:
        if pygame.key.get_pressed()[ pygame.K_RIGHT ] or (js!=None and js.get_axis(JS_XAXIS)>0) or (action == 0):
            if not thisLevel.CheckIfHitWall((player.x + player.speed, player.y), (player.nearestRow, player.nearestCol)): 
                player.velX = player.speed
                player.velY = 0
                
        elif pygame.key.get_pressed()[ pygame.K_LEFT ] or (js!=None and js.get_axis(JS_XAXIS)<0) or (action == 1):
            if not thisLevel.CheckIfHitWall((player.x - player.speed, player.y), (player.nearestRow, player.nearestCol)): 
                player.velX = -player.speed
                player.velY = 0
            
        elif pygame.key.get_pressed()[ pygame.K_DOWN ] or (js!=None and js.get_axis(JS_YAXIS)>0) or (action == 2):
            if not thisLevel.CheckIfHitWall((player.x, player.y + player.speed), (player.nearestRow, player.nearestCol)): 
                player.velX = 0
                player.velY = player.speed
            
        elif pygame.key.get_pressed()[ pygame.K_UP ] or (js!=None and js.get_axis(JS_YAXIS)<0) or (action == 3):
            if not thisLevel.CheckIfHitWall((player.x, player.y - player.speed), (player.nearestRow, player.nearestCol)):
                player.velX = 0
                player.velY = -player.speed

        if pygame.key.get_pressed()[ pygame.K_SPACE ]:
            global nextIteration
            nextIteration = True
                
    if pygame.key.get_pressed()[ pygame.K_ESCAPE ]:
        sys.exit(0)
            
    elif thisGame.mode == 3:
        # if pygame.key.get_pressed()[ pygame.K_RETURN ] or (js!=None and js.get_button(JS_STARTBUTTON)):
        thisGame.StartNewGame()
            

    
#      _____________________________________________
# ___/  function: Get ID-Tilename Cross References  \______________________________________ 
    
def GetCrossRef ():

    f = open(os.path.join(SCRIPT_PATH,"res","crossref.txt"), 'r')
    # ANDY -- edit
    #fileOutput = f.read()
    #str_splitByLine = fileOutput.split('\n')

    lineNum = 0
    useLine = False

    for i in f.readlines():
        # print " ========= Line " + str(lineNum) + " ============ "
        while len(i)>0 and (i[-1]=='\n' or i[-1]=='\r'): i=i[:-1]
        while len(i)>0 and (i[0]=='\n' or i[0]=='\r'): i=i[1:]
        str_splitBySpace = i.split(' ')
        
        j = str_splitBySpace[0]
            
        if (j == "'" or j == "" or j == "#"):
            # comment / whitespace line
            # print " ignoring comment line.. "
            useLine = False
        else:
            # print str(wordNum) + ". " + j
            useLine = True
        
        if useLine == True:
            tileIDName[ int(str_splitBySpace[0]) ] = str_splitBySpace[1]
            tileID[ str_splitBySpace[1] ] = int(str_splitBySpace[0])
            
            thisID = int(str_splitBySpace[0])
            if not thisID in NO_GIF_TILES:
                tileIDImage[ thisID ] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","tiles",str_splitBySpace[1] + ".gif")).convert()
            else:
                    tileIDImage[ thisID ] = pygame.Surface((16,16))
            
            # change colors in tileIDImage to match maze colors
            for y in range(0, 16, 1):
                for x in range(0, 16, 1):
                
                    if tileIDImage[ thisID ].get_at( (x, y) ) == (255, 206, 255, 255):
                        # wall edge
                        tileIDImage[ thisID ].set_at( (x, y), thisLevel.edgeLightColor )
                        
                    elif tileIDImage[ thisID ].get_at( (x, y) ) == (132, 0, 132, 255):
                        # wall fill
                        tileIDImage[ thisID ].set_at( (x, y), thisLevel.fillColor ) 
                        
                    elif tileIDImage[ thisID ].get_at( (x, y) ) == (255, 0, 255, 255):
                        # pellet color
                        tileIDImage[ thisID ].set_at( (x, y), thisLevel.edgeShadowColor )   
                        
                    elif tileIDImage[ thisID ].get_at( (x, y) ) == (128, 0, 128, 255):
                        # pellet color
                        tileIDImage[ thisID ].set_at( (x, y), thisLevel.pelletColor )   
                
            # print str_splitBySpace[0] + " is married to " + str_splitBySpace[1]
        lineNum += 1


#      __________________
# ___/  main code block  \_____________________________________________________

speedMultiplier = 4

#machine learning vars
steps = 50
score_req = 50
score_req_cap = 220
score_inc = 0.5
init_games = 100
renderGhosts = True
nextIteration = False
dataSizeLimit = 10000
learnRate = 1e-3
loadModel = False
epochs = 10
init_greed = 1
inc_greed = 0.05
final_greed = 0.1

#rewards
eatGhost = 5
eatDot = 10
lose = -100
time = -0.1
win = 100

# create the pacman
player = pacman()

# create a path_finder object
path = path_finder()

# create ghost objects
ghosts = {}
for i in range(0, 6, 1):
    # remember, ghost[4] is the blue, vulnerable ghost
    ghosts[i] = ghost(i)
    
# create piece of fruit
thisFruit = fruit()

tileIDName = {} # gives tile name (when the ID# is known)
tileID = {} # gives tile ID (when the name is known)
tileIDImage = {} # gives tile image (when the ID# is known)

# create game and level objects and load first level
thisGame = game()
thisLevel = level()
thisLevel.LoadLevel( thisGame.GetLevelNum() )

print(thisGame.screenSize)
window = pygame.display.set_mode( thisGame.screenSize, pygame.DOUBLEBUF | pygame.HWSURFACE )

# initialise the joystick
if pygame.joystick.get_count()>0:
  if JS_DEVNUM<pygame.joystick.get_count(): js=pygame.joystick.Joystick(JS_DEVNUM)
  else: js=pygame.joystick.Joystick(0)
  js.init()
else: js=None

observation = []

def renderGame(action, gen, iteration):
        CheckIfCloseButton( pygame.event.get() )
        
        if thisGame.mode == 1 or thisGame.mode == 5 or thisGame.mode == 6:
            if (thisGame.mode == 6):
                observation = player.map()
                reward = win
                dead = True
                return observation, reward, dead

            # normal gameplay mode
            CheckInputs(action)
            
            thisGame.modeTimer += 1
            observation, reward, dead = player.Move()
            if (renderGhosts == True):
                for i in range(0, 4, 1):
                    ghosts[i].Move()
            # thisFruit.Move()
                
        elif thisGame.mode == 2:
            # waiting after getting hit by a ghost
            thisGame.modeTimer += 1
            
            if thisGame.modeTimer >= 0:
                thisLevel.Restart()
                
                thisGame.lives -= 1
                if thisGame.lives == -1:
                    thisGame.updatehiscores(thisGame.score)
                else:
                    thisGame.SetMode( 4 )
                    
        elif thisGame.mode == 3:
            # game over
            CheckInputs(action)
                
        elif thisGame.mode == 4:
            # waiting to start
            thisGame.modeTimer += 1
            
            if thisGame.modeTimer >= 0:
                thisGame.SetMode( 1 )
                player.velX = player.speed
                
        elif thisGame.mode == 6:
            # pause after eating all the pellets
            thisGame.modeTimer += 1
            
            if thisGame.modeTimer >= 0:
                thisGame.SetMode( 7 )
                oldEdgeLightColor = thisLevel.edgeLightColor
                oldEdgeShadowColor = thisLevel.edgeShadowColor
                oldFillColor = thisLevel.fillColor
                
        elif thisGame.mode == 7:
            # flashing maze after finishing level
            thisGame.modeTimer += 1
            thisGame.SetMode ( 8 )
                
        elif thisGame.mode == 8:
            # blank screen before changing levels
            thisGame.modeTimer += 1
            if thisGame.modeTimer >= 0:
                thisGame.SetNextLevel()

        thisGame.SmartMoveScreen()
        
        screen.blit(img_Background, (0, 0))
        
        if not thisGame.mode == 8:
            thisLevel.DrawMap()

            thisGame.DrawNumber(gen, (5, 5))
            thisGame.DrawNumber(iteration, (5, 21))
            
            # if thisGame.fruitScoreTimer > 0:
            #     if thisGame.modeTimer % 2 == 0:
            #         thisGame.DrawNumber (2500, (thisFruit.x - thisGame.screenPixelPos[0] - 16, thisFruit.y - thisGame.screenPixelPos[1] + 4))

            for i in range(0, 4, 1):
                ghosts[i].Draw()
            # thisFruit.Draw()
            player.Draw()
            
            # if thisGame.mode == 3:
            #         screen.blit(thisGame.imHiscores,(32,256))
            
        # if thisGame.mode == 5:
        #     thisGame.DrawNumber (thisGame.ghostValue / 2, (player.x - thisGame.screenPixelPos[0] - 4, player.y - thisGame.screenPixelPos[1] + 6))
        
        
        
        # thisGame.DrawScore()
        
        pygame.display.flip()
        
        clock.tick (60)
        return observation, reward, thisGame.score, dead

def genData(x, model, gen):
    global nextIteration

    trainingData = []
    scores = []
    acceptedScores = []

    for iteration in range(x):
        thisGame.StartNewGame()
        memory = []
        predictions = []
        currObservation = []
        prevObservation = []
        prevAction = -1
        totalScore = 0

        won = False

        while True:
            greedy = random.uniform(0, 1.0)
            if (len(prevObservation) == 0) or (not model) or greedy < init_greed:
                action = random.randrange(0, 4)
            else:
                # prediction = model.predict(prevObservation.reshape(-1, len(prevObservation), 1))
                prediction = model.predict(np.array([observation]))
                action = np.argmax(prediction[0])

            observation, reward, score, dead = renderGame(action, gen, iteration + 1)
            predictions.append(observation)

            if (len(prevObservation) > 0):
                memory.append([observation, action])
            prevAction = action
            
            prevObservation = currObservation
            currObservation = observation
            totalScore += reward

            if dead and reward == win:
                won = True

            if dead or nextIteration:
                nextIteration = False
                break

        if (score >= score_req):
            acceptedScores.append(score)
            for data in memory:
                sample = [0, 0, 0, 0]
                # print(data[0])
                if data[1] >= 0:
                    sample[data[1]] = 1
                trainingData.append([data[0], sample])

        scores.append(score)
        print("Generation: ", gen, " | Iteration: ", iteration, " | Won: ", won, " | Score: ", "{0:10.4f}".format(totalScore, 5), " / ", score_req)

    # saveData = np.array([trainingData, score_req])
    # np.save('trainData.py', saveData)

    return trainingData

def reshapeData(data):
    if (len(data) > 0):
        obs = np.array([i[0] for i in data])
        direction = [i[1] for i in data]
    else:
            obs = []
            direction = []
    return obs, direction

def create_model(data):
    obs, direction = reshapeData(data)
    output_len = len(direction[0])
    # print(input_len, obs.shape, len(obs[0]), len(obs[0][0]), len(obs[0][0][0]))
    obs = np.float32(obs)
    neurNet = tflearn.layers.core.input_data(shape=[None, len(obs[0]), len(obs[0][0]), len(obs[0][0][0])])
    neurNet = tflearn.layers.conv.conv_2d(neurNet, 16, 3, strides = 1, activation="relu")
    neurNet = tflearn.layers.conv.conv_2d(neurNet, 32, 3, strides = 1, activation="relu")

    neurNet = tflearn.layers.core.fully_connected(neurNet, 256, activation="relu")
    neurNet = tflearn.layers.core.fully_connected(neurNet, output_len)
    neurNet = tflearn.layers.estimator.regression(neurNet, learning_rate=learnRate)
    model = tflearn.models.dnn.DNN(neurNet, tensorboard_dir="logs")

    return model

def fitModel(model, X, Y):
    model.fit(X, Y, n_epoch=epochs, batch_size=32, show_metric=True)
    model.save('pacman.tflearn')


def train():
    global steps, score_req, init_greed
    generation = 0
    increaseScore = True

    print("Generation ", generation)

    tempReq = score_req
    score_req = 20
    if loadModel == False:
        data = genData(init_games, None, generation)
    else:
        data = genData(10, None, generation)
    model = create_model(data)

    score_req = tempReq - score_inc

    if (loadModel == False):
        obs, direc = reshapeData(data)
        fitModel(model, obs, direc)
        generation += 1
    else:
        model.load('pacman.tflearn')
        generation += 1

    while True:
        if increaseScore == True and score_req < score_req_cap:
            score_req += score_inc
        else:
            increaseScore = True

        if init_greed > final_greed:
            init_greed -= inc_greed
            if init_greed < final_greed:
                init_greed = final_greed

        print("Generation ", generation)
        newData = genData(init_games, model, generation)

        if newData != []:
            data = newData
        else:
            increaseScore = False


        obs, direc = reshapeData(data)
        fitModel(model, obs, direc)
        generation += 1


train()