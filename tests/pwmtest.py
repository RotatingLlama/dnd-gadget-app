from machine import Pin, PWM
import time
from sys import exit

# 100% duty cycle
PWM_MAX = 65536

# We want to go up to 3v, out of a max of 3v3
MAX = int( PWM_MAX * (3/3.3) )

pin = Pin(17,Pin.OUT)

# duty of 0 seems to equate to 100%
# frequency of 50 Hz is enough to remove visible oscillation
# Frequency of 30kHz is comfortably outside the audible range
pwm = PWM(pin, freq=30000, duty_u16=1)

# Step through some positions
for i in range(9):
  dc = (MAX//8) * i
  pwm.duty_u16( dc )
  time.sleep(0.5)
time.sleep(2)


'''
# Oscillating tone
pos=int(MAX*0.9)
for i in range(32):
  pwm.init( freq=440, duty_u16=pos )
  time.sleep(0.2)
  pwm.init( freq=220, duty_u16=pos )
  time.sleep(0.2)
'''

time.sleep(5)

# Shut down without pegging to "on"
pwm.duty_u16( 1 )
pwm.deinit()
pin.off()

# Exit before we start singing
exit()

NOTE_B0  = 31
NOTE_C1  = 33
NOTE_CS1 = 35
NOTE_D1  = 37
NOTE_DS1 = 39
NOTE_E1  = 41
NOTE_F1  = 44
NOTE_FS1 = 46
NOTE_G1  = 49
NOTE_GS1 = 52
NOTE_A1  = 55
NOTE_AS1 = 58
NOTE_B1  = 62
NOTE_C2  = 65
NOTE_CS2 = 69
NOTE_D2  = 73
NOTE_DS2 = 78
NOTE_E2  = 82
NOTE_F2  = 87
NOTE_FS2 = 93
NOTE_G2  = 98
NOTE_GS2 = 104
NOTE_A2  = 110
NOTE_AS2 = 117
NOTE_B2  = 123
NOTE_C3  = 131
NOTE_CS3 = 139
NOTE_D3  = 147
NOTE_DS3 = 156
NOTE_E3  = 165
NOTE_F3  = 175
NOTE_FS3 = 185
NOTE_G3  = 196
NOTE_GS3 = 208
NOTE_A3  = 220
NOTE_AS3 = 233
NOTE_B3  = 247
NOTE_C4  = 262
NOTE_CS4 = 277
NOTE_D4  = 294
NOTE_DS4 = 311
NOTE_E4  = 330
NOTE_F4  = 349
NOTE_FS4 = 370
NOTE_G4  = 392
NOTE_GS4 = 415
NOTE_A4  = 440
NOTE_AS4 = 466
NOTE_B4  = 494
NOTE_C5  = 523
NOTE_CS5 = 554
NOTE_D5  = 587
NOTE_DS5 = 622
NOTE_E5  = 659
NOTE_F5  = 698
NOTE_FS5 = 740
NOTE_G5  = 784
NOTE_GS5 = 831
NOTE_A5  = 880
NOTE_AS5 = 932
NOTE_B5  = 988
NOTE_C6  = 1047
NOTE_CS6 = 1109
NOTE_D6  = 1175
NOTE_DS6 = 1245
NOTE_E6  = 1319
NOTE_F6  = 1397
NOTE_FS6 = 1480
NOTE_G6  = 1568
NOTE_GS6 = 1661
NOTE_A6  = 1760
NOTE_AS6 = 1865
NOTE_B6  = 1976
NOTE_C7  = 2093
NOTE_CS7 = 2217
NOTE_D7  = 2349
NOTE_DS7 = 2489
NOTE_E7  = 2637
NOTE_F7  = 2794
NOTE_FS7 = 2960
NOTE_G7  = 3136
NOTE_GS7 = 3322
NOTE_A7  = 3520
NOTE_AS7 = 3729
NOTE_B7  = 3951
NOTE_C8  = 4186
NOTE_CS8 = 4435
NOTE_D8  = 4699
NOTE_DS8 = 4978

melody = [
  NOTE_E7, NOTE_E7, 10, NOTE_E7,
  10, NOTE_C7, NOTE_E7, 10,
  NOTE_G7, 10, 10,  10,
  NOTE_G6, 10, 10, 10,

  NOTE_C7, 10, 10, NOTE_G6,
  10, 10, NOTE_E6, 10,
  10, NOTE_A6, 10, NOTE_B6,
  10, NOTE_AS6, NOTE_A6, 10,

  NOTE_G6, NOTE_E7, NOTE_G7,
  NOTE_A7, 10, NOTE_F7, NOTE_G7,
  10, NOTE_E7, 10, NOTE_C7,
  NOTE_D7, NOTE_B6, 10, 10,

  NOTE_C7, 10, 10, NOTE_G6,
  10, 10, NOTE_E6, 10,
  10, NOTE_A6, 10, NOTE_B6,
  10, NOTE_AS6, NOTE_A6, 10,

  NOTE_G6, NOTE_E7, NOTE_G7,
  NOTE_A7, 10, NOTE_F7, NOTE_G7,
  10, NOTE_E7, 10, NOTE_C7,
  NOTE_D7, NOTE_B6, 10, 10
]
tempo = [
  12, 12, 12, 12,
  12, 12, 12, 12,
  12, 12, 12, 12,
  12, 12, 12, 12,

  12, 12, 12, 12,
  12, 12, 12, 12,
  12, 12, 12, 12,
  12, 12, 12, 12,

  9, 9, 9,
  12, 12, 12, 12,
  12, 12, 12, 12,
  12, 12, 12, 12,

  12, 12, 12, 12,
  12, 12, 12, 12,
  12, 12, 12, 12,
  12, 12, 12, 12,

  9, 9, 9,
  12, 12, 12, 12,
  12, 12, 12, 12,
  12, 12, 12, 12,
]

def sing():

    for i in range(len(melody)):

      # to calculate the note duration, take one second
      # divided by the note type.
      # e.g. quarter note = 1000 / 4, eighth note = 1000/8, etc.
      noteDuration = 1000 / tempo[i]

      note( melody[i], noteDuration)

      # to distinguish the notes, set a minimum time between them.
      # the note's duration + 30% seems to work well:
      pauseBetweenNotes = noteDuration * 1.30
      time.sleep_ms( int(pauseBetweenNotes) )

      # stop the tone playing:
      note( 10, noteDuration)

def note( f,  length):
  pwm.init( freq=f, duty_u16=pos )
  time.sleep_ms(int(length))

sing()


pwm.duty_u16( 1 )