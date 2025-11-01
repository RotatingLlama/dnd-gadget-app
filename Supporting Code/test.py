n = 16
d = []

for i in range(n):
  d.append('a'+str(i))
  d.append('b'+str(i))

#print(d)

c=[]
for i in range(n):
  a = d[i] # The item we need to move
  b = d[i*2] # The item we want at i
  
  # Make the swap
  d[i] = b
  d[i*2] = a
  
  c.append(i)

print(c)
print(d[n:])