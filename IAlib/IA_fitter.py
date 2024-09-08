import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator

from IA_stats import *

class fitter(base):
    script_location = os.path.realpath(__file__)
    
    def __init__(self):
        return
    
    def backtrace_data(self, y, y_old, t, t_old, model_type='Osc', smth_index_rng=5, calc_ortho=False):
        #Used to fit the index data to the security data and extrapolate backwards
        #Creating security data that goes as far back as the index data
        
        if len(y_old) < len(y):
            #Inputs had been provided the wrong way round!
            tmp = y
            y = y_old.copy()
            y_old = tmp.copy()
            
        #Make the time direction consistent (past to present) 
        if t_old[-1] < t_old[0]:
            sort_old = np.argsort(t_old)
            y_old = y_old[sort_old]
            t_old = t_old[sort_old]
            
        if t[-1] < t[0]:
            sort_t = np.argsort(t)
            y = y[sort_t]
            t = t[sort_t]
            
        #Slice the old data to be on the same timescale as the security y_data (+ one element back)
        y_len = len(y)
        short_y_old = y_old[-(1+y_len):]
        short_t_old = t_old[-(1+y_len):]
        
        #Normalise y_old, t_old and y data:
        y_n_factor = max(y)
        y_norm = y / y_n_factor
        y_old_n_factor = max(short_y_old)
        y_old_norm = short_y_old / y_old_n_factor
        t_old_n_factor = short_t_old[-1]
        t_old_norm = short_t_old / t_old_n_factor
        
        #Create the input data
        comb_input = np.asarray([y_old_norm, t_old_norm])
        
        # Minimum frequency no. periods in security data interval:
        period_no = 1

        #Set model used and parameter bounds and estimates
        if model_type == 'Osc': #Oscillating model
            # Trigonometry amplitudes: can't be larger in magnitude than 1, otherwise there
            # can be negative values (as it can be larger growing exponential term at t -> 0)
            # Note, for damping exponentials (exp ratio < 0) it can be larger. However, as the area on which
            # the data is fitted will be the smallest point of the exponential, it would be part of the
            # fit and not something occuring solely in extrapolation. The fitting optimisation will prevent
            # these negative results and so limit the amplitude.
            # It can't be negative otherwise it creates cross-talk with the phase.
            # 
            # Trigonometric frequency: uses Nyquist frequency: y_len/2, but this needs to be
            # converted to angular frequency. The pi is already in the function and the 2 
            # is absorbed here --> y_len. 
            # Minimum scales inversely with the range of the data used. For period_no = 1,
            # the minimum frequency has 1 period in the data range. This is to ensure a
            # reasonable level of orthogonality between the exponential and sinusoidal term
            #
            # Trig. phase: between 0 and 1 (which corresponds to 0 and 2*pi in the function)
            #
            # Exponential ratio: Can be positive or negative (growth -> dividends or damping -> costs
            # and inefficiencies)
            
            
            min_freq = period_no / (t_old_norm[-1] - t_old_norm[0])
            param_bounds = (np.array([-np.inf, -np.inf,  0, 0, min_freq,   -np.inf]), \
                            np.array([ np.inf,  np.inf,  1, 1,    y_len/2,  np.inf]))
            estimate = np.array([0.5, 0, 0, 0.5, min_freq, 0])
            
            model = self.osc_backtrace_model
        elif model_type == 'Exp': #Model that's not oscillating
            param_bounds = (-np.inf, np.inf)
            estimate = np.array([0.5, 0, 1])
            model = self.exp_backtrace_model
            
        else:
            raise ValueError('The provided model type is unsuported.\n' + 'Either choose "Osc": '+\
                             'Oscillating exponential model, or "Exp": Purely exponential model.')

        #Peform the fitting
        popt, pcov, infodict, mesg, ier = curve_fit(model, comb_input, y_norm, \
                                bounds=param_bounds, p0=estimate, maxfev = 5000, full_output=True)

        if ier < 1 or ier > 4:
            raise ValueError('The fitting was not successful. The fit was exited with message: ' + mesg)
            
        
        # Scale the coefficients back:
        popt[:2] = popt[:2] * y_n_factor / y_old_n_factor
        
        #Condition number:
        condition_no_mag = np.log10(np.linalg.cond(pcov))
        
        # Scale the covariance matrix back:
        pcov[:2,:] = pcov[:2,:] * y_n_factor / y_old_n_factor
        pcov[:,:2] = pcov[:,:2] * y_n_factor / y_old_n_factor
        
        if model_type == 'Osc':
            # Scale the coefficients back:
            popt[4:] = popt[4:] / t_old_n_factor
            
            # Scale the covariance matrix back:
            pcov[4:,:] = pcov[4:,:] / t_old_n_factor
            pcov[:,4:] = pcov[:,4:] / t_old_n_factor
        else:
            # Scale the coefficients back:
            popt[2] = popt[2] / t_old_n_factor
            
            # Scale the covariance matrix back:
            pcov[2,:] = pcov[2,:] / t_old_n_factor
            pcov[:,2] = pcov[:,2] / t_old_n_factor
        
        backtrace = {'Parameters': popt}

        #The errors on the coefficients
        backtrace['Param. err'] = np.sqrt(np.diag(pcov))
        
        #Evaluate the fitted model and create the new data curve
        comb_input = np.asarray([y_old, t_old])
        fitted_y = model(comb_input, *popt)
        new_y = fitted_y.copy()
        new_y[-y_len:] = y  
        new_t = t_old[1:]
        
        #Use interpolation to smooth the transition from the fitted old data to the new data
        delete_indices = np.arange(-smth_index_rng,smth_index_rng+1, 1) - y_len
        gap_y = np.delete(new_y, delete_indices)
        gap_t = np.delete(new_t, delete_indices)
        smooth_y = PchipInterpolator(gap_t, gap_y)(new_t)
        
        #Calculate residuals:
        y_resid = infodict['fvec']*y_n_factor
        
        backtrace['Residuals'] = y_resid
        backtrace['Condition no. mag'] = condition_no_mag

        #Calculate R_adj^2:
        backtrace['R_adj^2'] = 1 - (np.sum(y_resid**2) / (y_len - len(popt))) / \
            (np.sum( (y - np.mean(y))**2 ) / (y_len - 1))
            
        #Calculate Durbin-Watson statistic
        backtrace['Durbin-Watson'] = np.sum((y_resid[1:] - y_resid[:-1])**2)/np.sum(y_resid[:-1]**2)
        
        #Calculate correlations:
        if model_type == 'Osc':
            #Exp and trig term fitted exp and sin vector correlations:
            exp_arr = np.exp(popt[5]*short_t_old[1:])
            trig_arr = np.sin(2*np.pi*(popt[4]*short_t_old[1:] + popt[3]))
            
            backtrace['Exp-trig corr'] = np.corrcoef(np.array([exp_arr, trig_arr]))[0,1]
            backtrace['Exp-trig orth'] = np.dot(exp_arr, trig_arr)/ (np.linalg.norm(exp_arr) * np.linalg.norm(trig_arr))


        #Correlation matrix of parameters
        backtrace['Correlation mtrx'] = pcov / np.sqrt(np.expand_dims(np.diag(pcov),0) * np.expand_dims(np.diag(pcov),1))


        if calc_ortho:
            freq = period_no / (1 - t_old_norm[0])
            phase_arr = np.expand_dims(np.linspace(0,1,20), 0)
            
            
            max_ind = (20, 0)
            opt_exp = 1
            iterations = 0
            
            #Repeat in case the maximum is not within the initial range
            while max_ind[0] == 20 or iterations == 50:
                exp_rat_arr = np.expand_dims(np.linspace(opt_exp,opt_exp+50,20), 1)

                ortho = self.exp_trig_ortho(exp_rat_arr, phase_arr, freq, t_old_norm[0])
                
                max_ind = np.unravel_index(np.argmax(ortho), ortho.shape)
                
                opt_exp = exp_rat_arr[max_ind[0],0]
                
                iterations += 1
            
            if iterations == 50:
                raise ValueError('Maximum orthogonality could not be determined within 50 iterations. \n'+\
                        'The peak lies higher than exponential ratio = 2500!')
            
            opt_phase = phase_arr[0,max_ind[1]]

            s_phase_arr = np.expand_dims(np.linspace(opt_phase-0.05,opt_phase+0.05,51), 0)
            s_exp_rat_arr = np.expand_dims(np.linspace(opt_exp-1.5,opt_exp+1.5,51), 1)
            
            ortho = self.exp_trig_ortho(s_exp_rat_arr, s_phase_arr, freq, t_old_norm[0])

            backtrace['Max exp_trig orth'] = np.max(ortho)

        
        return smooth_y, new_t, backtrace

                                                                
    def exp_backtrace_model(self, x, a, b, exp_rat):
        # Define the function to be fitted:
        # Linear model that also includes the t-1 term, this incorporates lagging
        # As well as a term proportional to the direction of the curve (return)
        # y = c1*y + c2*y_lag + c3*(y - y_lag)
        # --> y = (c1 + c3)*y + (c2 - c3)*y_lag
        # --> y = a*y + b*y_lag
        #
        #
        # To include the effect of accumulating dividends, stock lending profits against
        # management costs, potential currency hedging costs and inefficiencies, this is 
        # multiplied with an exponential term, which varies with time.
        #
        # This is multiplied with the full y and y_lag term, also to not add cross-talk between
        # the exponential element and the lagging.
        
        return (a*x[0,1:] + b*x[0,:-1])*np.exp(exp_rat*x[1,1:]) 

                                                                
    def osc_backtrace_model(self, x, a, b, amp_sin, phase, freq, exp_rat):
        # Define the function to be fitted:
        # Linear model that also includes the t-1 term, this incorporates lagging
        # As well as a term proportional to the direction of the curve (return)
        # y = c1*y + c2*y_lag + c3*(y - y_lag)
        # --> y = (c1 + c3)*y + (c2 - c3)*y_lag
        # --> y = a*y + b*y_lag
        #
        # To include the effect of accumulating dividends, stock lending profits against
        # management costs, potential currency hedging costs and inefficiencies, this is 
        # multiplied with an exponential term, which varies with time.
        #
        # This is multiplied with the full y and y_lag term, also to not add cross-talk between
        # the exponential element and the lagging.
        #
        # Furthermore, a sinusoidal term is added to account for non-linear discrepencies
        # between the index and the security caused by periodic behaviour (market downturns affecting
        # things like dividend payouts or currency hedging costs)
        #
        # To make the phase inside the sine fcn more orthogonal to the frequency and amplitude,
        # the -f*x0 term is added, keeping the phase stable at the start of the dataset for varying
        # frequency (rather than being stable at 0 which is outside the dataset).
        
        return (a*x[0,1:] + b*x[0,:-1])*(np.exp(exp_rat*x[1,1:]) + \
                          amp_sin*np.sin(2*np.pi*(freq*x[1,1:] + (phase - freq*x[1,1]))))
         
            
    def exp_trig_ortho(self, R, phase, freq, a):
        # The orthogonality of the exponential term e^(Rx) with a sinusoidal term sin(freq*x + phase)
        
        #Exp_ratio, phase, freq, lower_limit (upper limit is 1 -> t data is normalised)
        p = 2*np.pi * phase
        f = 2*np.pi * freq
        
        
        projection = (np.exp(R) * (R*np.sin(f + p) - f*np.cos(f + p)) - \
            np.exp(R*a) * (R * np.sin(f*a + p) - f * np.cos(f + p))) / (f**2 + R**2)
        
        norm_exp = np.sqrt((np.exp(2*R) - np.exp(2*R*a))/(2*R))
        
        norm_trig = np.sqrt((2*f*(1-a) + np.sin(2*(f*a + p)) - np.sin(2*(f + p)))/(4*f))
        
        return abs(projection / (norm_exp * norm_trig))
    