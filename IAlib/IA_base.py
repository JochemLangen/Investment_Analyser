# -*- coding: utf-8 -*-

import os
import sys
import numpy as np
import pandas as pd


class base:
    script_location = os.path.realpath(__file__)
    
    def __init__(self):
        return
    
    def perform_task(self, elements, task, *args, **kwargs):
        print('Processing task: ', task)
        nelem = len(elements)
        if nelem != 0:
            # Determine the step increment for the process bar:
            processing_inc = round(100/nelem, 2)
            
            func = getattr(self, task)
            
            # Loop through all files and convert them to xlsx:
            for i, item in enumerate(elements):
                self.process_bar(i*processing_inc, item)            
                func(item, *args, **kwargs)
        else:
            item = 'Nothing to be done'
        # Done!    
        self.process_bar(100, item)
        print('\n')
        return
    
    def process_bar(self, inc, element):
        sys.stdout.write('\r')
        sys.stdout.write("[%-50s] %5.2f%% Current element: %s                                   "\
                         % ('='*int(inc//2), inc, element))
        sys.stdout.flush()
        return
    
    def __str__(self):
        output = str('Class: ' + self.__class__.__name__ + ' \n Attributes: \n')
        for attr, val in self.__dict__.items():
            if isinstance(val, list) or isinstance(val, np.ndarray) or \
                isinstance(val, pd.core.frame.DataFrame):
                output += str('  '+ attr + ': {}\n'.format(type(val)))
            else:
                output += str('  '+ attr + ": " + str(val) +' \n')
        return output