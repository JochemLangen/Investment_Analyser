import numpy as np

from IA_base import *

class stats(base):
    script_location = os.path.realpath(__file__)
    
    def __init__(self):
        return
    
    def calc_std_1D(self, y_mx, time, axis=1):
        # Only 2D (matrix) is supported
        #Make sure y_mx is numpy array and turn into percentile data
        y_mx = np.asarray(y_mx)*100
        
        #Set up STD matrix, mean and std
        other_axis = (axis-1)%2
        std_array = np.empty((np.shape(y_mx)[other_axis], 4))
        
        #STD error array, SE and uncertainty in std
        std_err = std_array.copy()
        
        #Calculate the std array:
        std_array[:,0] = np.nanmean(y_mx, axis=axis)
        std_array[:,1] = np.nanstd(y_mx, axis=axis, ddof=1)
        
        #Calculate the length of each population data (i.e. non-nan values)
        valid_entries = np.sum(~np.isnan(y_mx), axis=axis)
        
        #Calcualte the uncertainty on the mean and standard deviation
        std_err[:,0] = std_array[:,1]/np.sqrt(valid_entries) #STD/sqrt(n)
        std_err[:,1] = std_array[:,1]/np.sqrt(2*valid_entries - 2) #STD/sqrt(2*n -2)
        
        
        ## Calculate annualised returns
        annualised_y_mx = self.__annualise(time,y_mx)[0,:,:]
        
        #Calculate avg and std on annualised y_mx
        std_array[:,2] = np.nanmean(annualised_y_mx, axis=axis)
        std_array[:,3] = np.nanstd(annualised_y_mx, axis=axis, ddof=1)
        
        #Calcualte the uncertainty on the mean and standard deviation
        std_err[:,2] = std_array[:,3]/np.sqrt(valid_entries) #STD/sqrt(n)
        std_err[:,3] = std_array[:,3]/np.sqrt(2*valid_entries - 2) #STD/sqrt(2*n -2)
        
        return std_array, std_err
    
    def calc_std_2D(self, time, y_mx, coeff, *args):
        #First half of args are y_mx, second half are the coefficients
        #Can also be used for the 1D case
        
        #Extract the arguments
        nargs = len(args)
        y_matrices = args[0:nargs:2] #Extract the uneven *args -> y_mx
        coeffs = args[1:nargs:2] #Extract the even *args -> coeffs

        y_mat = np.asarray([y_mx, *y_matrices])*100
        
        #Calculate the covariance matrix, note this method was used as it will be
        # the same as for the fitting
        results_tens, y_tens, N = self.__calc_cov(*y_mat)
        
        ## Calculate annualised covariance matrix
        annualised_y_mat = self.__annualise(time, *y_mat)

        ann_results_tens = self.__calc_cov(*annualised_y_mat)[0]
        
        #Combine the covariance matrix data to find the mean and std for each time interval point
        std_array, std_err, return_series = self.__comb_std(results_tens, ann_results_tens, \
                                           y_tens, N, coeff, *coeffs)
        
        return std_array, std_err, return_series
    
    def __calc_cov(self, y_mx, *args, **kwargs):
        #Args must be y_mx arrays
        #Parse kwargs
        axis = kwargs.get("axis", 1)
        
        #Combine all y_mx array inputs
        y_tens = np.stack([y_mx, *args], axis=2)
        
        #Residual tensor
        means_tens = np.nanmean(y_tens, axis=axis, keepdims=True)
        resid_tens = y_tens - means_tens
        
        # 3D tensor with 1 direction being the time series of the covariance residuals
        # (x_i - x_mean)(y_i - y_mean), the other the time interval used for the series and the other the
        # combination of the variables used (i.e. the combination of the original y_mx, i.e. x and y)
        # cov_tens 
        y_shape = np.shape(y_tens)
        cov_tens = np.empty((y_shape[0], y_shape[1], y_shape[2], y_shape[2]))
        
        #Create the upper triangular matrix
        for i in range(y_shape[2]):
            cov_tens[:,:,i,:] = resid_tens[:,:,[i]] * resid_tens[:,:,:]
        
        #Extend to the lower triangular matrix:
        # cov_tens = cov_tens + np.transpose(cov_tens, axes=(0,1,3,2)) - np.diagonal(cov_tens, axis1=2, axis2=3, keepdims=True)

        # Calculate tensor sums (which can be added to get the total std)
        N = np.sum(~np.isnan(y_tens), axis=axis, keepdims=True)[:,:,[0]] #Take the sum of non-nan values of first security, should be the same for all
        cov_sum = np.nansum(cov_tens, axis=axis)/(N - 1)
        
        #First row along second axis is the means, rather than the covariances
        results_tens = np.append(means_tens, cov_sum, axis=axis)

        return results_tens, y_tens, N
    
    def __comb_std(self, cov_tens, ann_cov_tens, y_tens, N, coeff, *args):

        #Set up STD matrix, mean and std
        std_array = np.empty((np.shape(cov_tens)[0], 4))
        
        #STD error array, SE and uncertainty in std
        std_err = std_array.copy()

        #Create tensor of coefficients
        coeff_arr = np.array([coeff, *args])
        coeff_mat = np.expand_dims(coeff_arr, axis=0) #Axis 0 has the time interval dimension
        coeff_tens = np.dstack([coeff_mat]*len(coeff_arr))
        
        #Get the square of the coefficients to be used for the covariance
        coeff_sqrd = np.transpose(coeff_tens, axes=(0,2,1)) * coeff_tens
        
        #Calculate the std array:
        std_array[:,0] = np.sum(cov_tens[:,0,:] * coeff_mat, axis=1)
           
        w_cov_tens = cov_tens[:,1:,:] * coeff_sqrd
        std_array[:,1] = np.sqrt(np.sum(w_cov_tens, axis=(1,2)))
        
        #Calcualte the uncertainty on the mean and standard deviation
        std_err[:,0] = std_array[:,1]/np.sqrt(N[:,0,0]) #STD/sqrt(n)
        std_err[:,1] = std_array[:,1]/np.sqrt(2*N[:,0,0] - 2) #STD/sqrt(2*n -2)
        
        
        ## Calculate annualised std array:
        std_array[:,2] = np.sum(ann_cov_tens[:,0,:] * coeff_mat, axis=1)
           
        w_ann_cov_tens = ann_cov_tens[:,1:,:] * coeff_sqrd
        std_array[:,3] = np.sqrt(np.sum(w_ann_cov_tens, axis=(1,2)))
        
        #Calcualte the uncertainty on the mean and standard deviation
        std_err[:,2] = std_array[:,3]/np.sqrt(N[:,0,0]) #STD/sqrt(n)
        std_err[:,3] = std_array[:,3]/np.sqrt(2*N[:,0,0] - 2) #STD/sqrt(2*n -2)
        
        #Calculate the return series for the combined portfolio
        y_series_mat = np.sum(y_tens * coeff_mat, axis=2)
        
        return std_array, std_err, y_series_mat
    
    def __annualise(self, time, y_mx, *args):
        #Extract matrices expressed in percentages:
        y_matrices = np.array([y_mx, *args]) 
        
        #Expand time array into matrix format
        time_mat = np.expand_dims(time, axis=1)

        #Convert y_mx into fractional data, get annualised return and convert back to % gain
        #using the absolute and sign are there in case of debt
        annualised_y_mat = ((1 + y_matrices/100)**[12/time_mat] - 1)*100
        
        return annualised_y_mat