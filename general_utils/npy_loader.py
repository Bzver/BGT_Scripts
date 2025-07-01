import numpy
import os

npyDir = os.path.join('D:\\', 'Project', 'sdannce', 'demo', 'SCN2A_SOC1_2022_09_23_M1_M6', 'videos', 'Camera1')
npyFile = os.path.join(npyDir,'frametimes.npy')
data = numpy.load(npyFile)
