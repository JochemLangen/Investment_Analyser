import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

from IA_stats import *

class fitter(base):
    script_location = os.path.realpath(__file__)
    
    def __init__(self):
        return
    
    def backtrace_data(self, y, y_old, t, t_old):
        #Used to fit the index data to the security data and extrapolate backwards
        #Creating security data that goes as far back as the index data
        
        if len(y_old) < len(y):
            #Inputs had been provided the wrong way round!
            tmp = y
            y = y_old.copy()
            y_old = tmp.copy()
            
        #Slice the old data:
        y_len = len(y)
        short_y_old = y_old[-y_len:]
        
        lin_func = lambda x, a, b: a*x + b
        popt, pcov = curve_fit(lin_func, short_y_old, y)
        
        new_y = lin_func(y_old, *popt)
        fitted_y = new_y.copy()
        
        new_y[-y_len:] = y
        print(new_y)
        print(*popt)
        print(pcov)
        
        fig = plt.figure()
        # plt.plot(t_old, y_old, label='index')
        plt.plot(t_old, fitted_y, label='fitted')
        plt.plot(t, y, label='orig')
        plt.legend()
        plt.show()
        
        plt.figure()
        plt.plot(t, (fitted_y[-y_len:]-y)/y)
        plt.show()
        
        
        return
    