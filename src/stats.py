import numpy as np
from os.path import realpath
from investment_analyser.base import Base


class Stats(Base):
    script_location = realpath(__file__)

    def __init__(self):
        return

    def calc_std_1D(self, y_mx, time, axis=1):
        """Calculate statistics for a 1D return matrix.

        Parameters
        ----------
        y_mx : array_like
            2D matrix of returns expressed as fractions; multiplied by 100 internally.
        time : array_like
            Time intervals used for annualisation.
        axis : int, default 1
            Axis along which to calculate statistics.

        Returns
        -------
        std_array : ndarray, shape (n_periods, 8)
            Columns contain:
            0: mean
            1: std
            2: downside semistd (multiplied by 2 to be the same magnitude as regular std)
            3: upside semistd (*)
            4: annualised mean
            5: annualised std
            6: annualised downside semistd (*)
            7: annualised upside semistd (*)
        std_err : ndarray, shape (n_periods, 8)
            Standard error / uncertainty for corresponding std_array columns.
        """
        # Ensure floats
        time = np.asarray(time, dtype=float)

        # Only 2D (matrix) is supported
        # Make sure y_mx is numpy array and turn into percentile data
        y_mx = np.asarray(y_mx) * 100

        # Set up STD matrix, mean and std
        other_axis = (axis - 1) % 2
        std_array = np.empty((np.shape(y_mx)[other_axis], 8))

        # STD error array, SE and uncertainty in std
        std_err = std_array.copy()

        # Calculate the std array:
        mean = np.nanmean(y_mx, axis=axis)
        std_array[:, 0] = mean
        std_array[:, 1] = np.nanstd(y_mx, axis=axis, ddof=1)

        n_elem = np.shape(y_mx)[axis]

        # Calculate the downside and upside semivariance
        mean_expanded = np.expand_dims(mean, axis=axis)
        downside_var = (
            2
            * np.nanmean(np.square(np.maximum(0, mean_expanded - y_mx)), axis=axis)
            * n_elem
            / (n_elem - 1)
        )
        upside_var = (
            2
            * np.nanmean(np.square(np.maximum(0, y_mx - mean_expanded)), axis=axis)
            * n_elem
            / (n_elem - 1)
        )
        std_array[:, 2] = np.sqrt(downside_var)
        std_array[:, 3] = np.sqrt(upside_var)

        # Calculate the length of each population data (i.e. non-nan values)
        valid_entries = np.sum(~np.isnan(y_mx), axis=axis)

        # Calcualte the uncertainty on the stds
        std_err[:, 0] = std_array[:, 1] / np.sqrt(valid_entries)  # STD/sqrt(n)
        std_err[:, 1] = std_array[:, 1] / np.sqrt(2 * valid_entries - 2)  # STD/sqrt(2*n -2)
        std_err[:, 2] = std_array[:, 2] / np.sqrt(2 * valid_entries - 2)  # semistd/sqrt(2*n -2)
        std_err[:, 3] = std_array[:, 3] / np.sqrt(2 * valid_entries - 2)  # semistd/sqrt(2*n -2)

        ## Calculate annualised returns
        annualised_y_mx = self.__annualise(time, y_mx)[0, :, :]

        # Calculate avg and std on annualised y_mx
        annual_mean = np.nanmean(annualised_y_mx, axis=axis)
        std_array[:, 4] = annual_mean
        std_array[:, 5] = np.nanstd(annualised_y_mx, axis=axis, ddof=1)

        # Calculate the downside and upside semivariance for annualised returns
        annual_mean_expanded = np.expand_dims(annual_mean, axis=axis)
        annual_downside_var = (
            2
            * np.nanmean(
                np.square(np.maximum(0, annual_mean_expanded - annualised_y_mx)), axis=axis
            )
            * n_elem
            / (n_elem - 1)
        )
        annual_upside_var = (
            2
            * np.nanmean(
                np.square(np.maximum(0, annualised_y_mx - annual_mean_expanded)), axis=axis
            )
            * n_elem
            / (n_elem - 1)
        )
        std_array[:, 6] = np.sqrt(annual_downside_var)
        std_array[:, 7] = np.sqrt(annual_upside_var)

        # Calcualte the uncertainty on the mean and standard deviation
        std_err[:, 4] = std_array[:, 5] / np.sqrt(valid_entries)  # STD/sqrt(n)
        std_err[:, 5] = std_array[:, 5] / np.sqrt(2 * valid_entries - 2)  # STD/sqrt(2*n -2)
        std_err[:, 6] = std_array[:, 6] / np.sqrt(2 * valid_entries - 2)  # semistd/sqrt(2*n -2)
        std_err[:, 7] = std_array[:, 7] / np.sqrt(2 * valid_entries - 2)  # semistd/sqrt(2*n -2)

        return std_array, std_err

    def calc_std_2D(self, time, y_mx, coeff, *args):
        # First half of args are y_mx, second half are the coefficients
        # Can also be used for the 1D case

        # Extract the arguments
        nargs = len(args)
        # THe input is return matrix and coefficients in pairs:
        y_matrices = args[0:nargs:2]  # Extract the uneven *args -> y_mx
        coeffs = args[1:nargs:2]  # Extract the even *args -> coeffs

        y_mat = np.asarray([y_mx, *y_matrices]) * 100

        # Calculate the covariance matrix, note this method was used as it will be
        # the same as for the fitting
        means, cov, hedging_cov, gains_cov, n_elem, y_tens = self.calc_cov(*y_mat)

        ## Calculate annualised covariance matrix
        annualised_y_mat = self.__annualise(time, *y_mat)

        ann_means, ann_cov, ann_hedging_cov, ann_gains_cov, _, _ = self.calc_cov(*annualised_y_mat)

        # Combine the covariance matrix data to find the mean and std for each time interval point
        std_array, std_err, return_series = self.__comb_std(
            means,
            cov,
            hedging_cov,
            gains_cov,
            ann_means,
            ann_cov,
            ann_hedging_cov,
            ann_gains_cov,
            n_elem,
            y_tens,
            coeff,
            *coeffs,
        )

        return std_array, std_err, return_series

    def calc_cov(self, y_mx, *args, **kwargs):
        # Args must be y_mx arrays
        # Parse kwargs
        axis = kwargs.get("axis", 1)

        # Combine all y_mx array inputs
        y_tens = np.stack([y_mx, *args], axis=2)

        # Residual tensor
        means_tens = np.nanmean(y_tens, axis=axis, keepdims=True)
        resid_tens = y_tens - means_tens

        # 3D tensor with 1 direction being the time series of the covariance residuals
        # (x_i - x_mean)(y_i - y_mean), the other the time interval used for the series and the other the
        # combination of the variables used (i.e. the combination of the original y_mx, i.e. x and y)
        # cov_tens
        cov_tens = resid_tens[:, :, :, None] * resid_tens[:, :, None, :]

        # Calculate tensor sums (which can be added to get the total std)
        n_elem = np.sum(~np.isnan(y_tens), axis=axis, keepdims=True)[
            :, :, [0]
        ]  # Take the sum of non-nan values of first security, should be the same for all
        cov_sum = np.nansum(cov_tens, axis=axis) / (n_elem - 1)

        # The variance consists of four terms:
        # Both delta terms are positive: del_1 * del_2
        # Both delta terms are negative: -del_1 * -del_2
        # The first delta term is postive and the second negative: del_1 * -del_2
        # The first delta term is negative and the second positive: -del_1 * del_2
        #
        # Where the delta is |mean - value|
        # For self-correlation, only the first two terms occur (as del_1 == del_2, they are always have the same sign)
        # So, to scale the downside_variance to be the same magnitude as the standard deviation, it should be multiplied
        # by a factor of 2 for self-correlation.
        #
        # For correlation between two different variables, it should be multiplied by two but only to have the same scale
        # as the net positive terms (so both del_1 and del_2) have the same sign.
        # The total hedging_std is therefore: 2*downside_var (both negative) + anticorr_var (both mixed terms together)

        # Calculate the downside covariance sum, only including pairs where both
        # residuals are negative.
        downside_mask = np.logical_and(
            resid_tens[:, :, :, None] < 0,
            resid_tens[:, :, None, :] < 0,
        )
        downside_cov_sum = (
            2 * np.nansum(np.where(downside_mask, cov_tens, np.nan), axis=axis) / (n_elem - 1)
        )

        # Calculate the upside covariance sum, only including pairs where both
        # residuals are positive.
        upside_mask = np.logical_and(
            resid_tens[:, :, :, None] > 0,
            resid_tens[:, :, None, :] > 0,
        )
        upside_cov_sum = (
            2 * np.nansum(np.where(upside_mask, cov_tens, np.nan), axis=axis) / (n_elem - 1)
        )

        # Anticorrelation cov sum (where one is positive and the other negative)
        anticorr_mask = np.logical_and(~downside_mask, ~upside_mask)
        anticorr_cov_sum = np.nansum(np.where(anticorr_mask, cov_tens, np.nan), axis=axis) / (
            n_elem - 1
        )

        hedging_cov_sum = downside_cov_sum + anticorr_cov_sum
        gains_cov_sum = upside_cov_sum + anticorr_cov_sum

        return means_tens, cov_sum, hedging_cov_sum, gains_cov_sum, n_elem, y_tens

    def __comb_std(
        self,
        means,
        cov,
        hedging_cov,
        gains_cov,
        ann_means,
        ann_cov,
        ann_hedging_cov,
        ann_gains_cov,
        n_elem,
        y_tens,
        coeff,
        *args,
    ):
        """Combine covariance results into portfolio statistics."""
        # Set up STD matrix, mean and std
        std_array = np.empty((np.shape(means)[0], 8))

        # STD error array, SE and uncertainty in std
        std_err = std_array.copy()

        # Create tensor of coefficients
        coeff_arr = np.array([coeff, *args])
        coeff_mat = np.expand_dims(coeff_arr, axis=0)  # Axis 0 has the time interval dimension
        coeff_tens = np.dstack([coeff_mat] * len(coeff_arr))

        # Get the square of the coefficients to be used for the covariance
        coeff_sqrd = np.transpose(coeff_tens, axes=(0, 2, 1)) * coeff_tens

        # Calculate the std array:
        std_array[:, 0] = np.sum(means * coeff_mat, axis=1)
        std_array[:, 1] = np.sqrt(np.sum(cov * coeff_sqrd, axis=(1, 2)))
        std_array[:, 2] = np.sqrt(np.sum(hedging_cov * coeff_sqrd, axis=(1, 2)))
        std_array[:, 3] = np.sqrt(np.sum(gains_cov * coeff_sqrd, axis=(1, 2)))

        # Calcualte the uncertainty on the mean and standard deviation
        std_err[:, 0] = std_array[:, 1] / np.sqrt(n_elem[:, 0, 0])  # STD/sqrt(n)
        std_err[:, 1] = std_array[:, 1] / np.sqrt(2 * n_elem[:, 0, 0] - 2)  # STD/sqrt(2*n -2)
        std_err[:, 2] = std_array[:, 2] / np.sqrt(2 * n_elem[:, 0, 0] - 2)  # semistd/sqrt(2*n -2)
        std_err[:, 3] = std_array[:, 3] / np.sqrt(2 * n_elem[:, 0, 0] - 2)  # semistd/sqrt(2*n -2)

        ## Calculate annualised std array:
        std_array[:, 4] = np.sum(ann_means * coeff_mat, axis=1)
        std_array[:, 5] = np.sqrt(np.sum(ann_cov * coeff_sqrd, axis=(1, 2)))
        std_array[:, 6] = np.sqrt(np.sum(ann_hedging_cov * coeff_sqrd, axis=(1, 2)))
        std_array[:, 7] = np.sqrt(np.sum(ann_gains_cov * coeff_sqrd, axis=(1, 2)))

        # Calcualte the uncertainty on the mean and standard deviation
        std_err[:, 4] = std_array[:, 5] / np.sqrt(n_elem[:, 0, 0])  # STD/sqrt(n)
        std_err[:, 5] = std_array[:, 5] / np.sqrt(2 * n_elem[:, 0, 0] - 2)  # STD/sqrt(2*n -2)
        std_err[:, 6] = std_array[:, 6] / np.sqrt(2 * n_elem[:, 0, 0] - 2)  # semistd/sqrt(2*n -2)
        std_err[:, 7] = std_array[:, 7] / np.sqrt(2 * n_elem[:, 0, 0] - 2)  # semistd/sqrt(2*n -2)

        # Return series
        y_series_mat = np.sum(y_tens * coeff_mat, axis=2)

        return std_array, std_err, y_series_mat

    def __annualise(self, time, y_mx, *args):
        # Extract matrices expressed in percentages:
        y_matrices = np.array([y_mx, *args])

        # Expand time array into matrix format
        time_mat = np.expand_dims(time, axis=1)

        # Convert y_mx into fractional data, get annualised return and convert back to % gain
        # using the absolute and sign are there in case of debt
        annualised_y_mat = ((1 + y_matrices / 100) ** [12 / time_mat] - 1) * 100

        return annualised_y_mat
