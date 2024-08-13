import numpy as np

from IA_base import *

class stats(base):
    script_location = os.path.realpath(__file__)
    
    def __init__(self):
        return
    
    def calc_std(self, y_mx, axis=1):
        # Only 2D (matrix) is supported
        y_mx = np.asarray(y_mx)
        
        #Set up STD matrix, mean and std
        other_axis = (axis-1)%2
        std_array = np.empty((np.shape(y_mx)[other_axis], 2))
        
        #STD error array, SE and uncertainty in std
        std_err = std_array.copy()
        
        #Calculate the std array:
        std_array[:,0] = np.nanmean(y_mx, axis=axis)
        std_array[:,1] = np.nanstd(y_mx, axis=axis)
        
        valid_entries = np.sum(~np.isnan(y_mx), axis=axis)
        
        std_err[:,0] = std_array[:,1]/np.sqrt(valid_entries) #STD/sqrt(n)
        std_err[:,1] = std_array[:,1]/np.sqrt(2*valid_entries - 2) #STD/sqrt(2*n -2)
        return std_array, std_err