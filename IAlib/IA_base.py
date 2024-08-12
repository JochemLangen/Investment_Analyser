# -*- coding: utf-8 -*-

import os
import sys


class base:
    script_location = os.path.realpath(__file__)
    
    def __init__(self):
        return
    
    def perform_task(self, elements, task, *args):
        
        nelem = len(elements)
        if nelem != 0:
            # Determine the step increment for the process bar:
            processing_inc = round(100/nelem, 2)
            
            func = getattr(self, task)
            
            # Loop through all files and convert them to xlsx:
            for i, item in enumerate(elements):
                self.__process_bar(i*processing_inc, item)            
                func(item, *args)
            
        # Done!    
        self.__process_bar(100, item)
        return
    
    def __process_bar(self, inc, element):
        sys.stdout.write('\r')
        sys.stdout.write("[%-50s] %5.2f%% Current element: %s            " % ('='*int(inc//2), inc, element))
        sys.stdout.flush()
        return
    
    # def __str__(self):
    #     output = str(self.__class__.__name__ + '\n')
    #     for attr, val in self.__dict__.items():
    #         output += str(attr + ": " + str(val) +'\n')
    #     return output