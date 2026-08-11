import fnmatch
import os
import pickle
import re

import numpy as np
import pandas as pd
import pyautogui
from investment_analyser.backtrace import Backtrace
from investment_analyser.data_loader import DataLoader
from investment_analyser.plotter import Plotter
from investment_analyser.security import Security, STANDARD_MONTH_SIZE
from scipy.optimize import minimize

MARKET_FACTOR_SECURITY = "*Core*S&P*500*"


class Portfolio(Security, Plotter, DataLoader, Backtrace):
    script_location = os.path.realpath(__file__)

    def __init__(
        self,
        data_location=os.path.realpath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "data", "data.xlsx")
        ),
        months=[],
        start_date=None,
        load=False,
        overwrite_new_file_names=False,
        fetch_data=None,  # Can be "All", "non-fx", "securities", "indices" or "fx"
    ):

        Plotter.__init__(self)
        DataLoader.__init__(self)

        self.dataframe = pd.read_excel(data_location)
        valid_securities = self.dataframe["Name"].notnull()

        # Check whether all the data has been fetched:
        if fetch_data is not None:
            self.fetch_data(which=fetch_data)
        elif (
            self.dataframe["Index_loc"][valid_securities].isnull().values.any()
            or self.dataframe["Security_loc"][valid_securities].isnull().values.any()
        ):
            answer = pyautogui.confirm(
                text="Not all securities have their file locations defined.\n"
                + "Would you like to fetch all data? This may take some time.\n"
                + "If not, an attempt will be made to use the available data.",
                title="Missing Index or Security data",
                buttons=["Yes", "No"],
            )
            if answer == "Yes":
                self.fetch_data()

        # Load all the securities from the data folder into a dictionary
        self.securities = {}
        self.perform_task(
            self.dataframe["Name"][valid_securities],
            "load_securities",
            load=load,
            fx_df=self.dataframe[["Currency", "Currency_loc"]].dropna(),
        )
        security_names = list(self.securities.keys())

        if (
            overwrite_new_file_names == True and load == False and "answer" not in locals()
        ):  # Otherwise the files are reloaded i.e. had been processed before so these names should already be good
            self.dataframe["Name"][valid_securities] = security_names
            self.save_dataframe()

        # Calculate the return matrices per security:
        self.perform_task(
            security_names, "calc_return_matrix_per_security", months=months, start_date=start_date
        )

        self.months = self.securities[security_names[0]].months

        return

    def plot_portfolio(
        self, coef_type="Fitted_coef", std_mult=[1, 2, 3], limit=2, time_index=-1, coeffs=None
    ):
        # Plot the portfolio

        # Generate the input list to pass to calc_std_2D
        input_list = [self.months]

        if coeffs == None:  # Use coeffs from dataframe
            for index, element in enumerate(list(self.securities.keys())):
                input_list += [
                    self.securities[element].return_matrix,
                    self.dataframe[coef_type][index],
                ]
        else:  # manual input of coeffs for this function
            for index, element in enumerate(list(self.securities.keys())):
                input_list += [self.securities[element].return_matrix, coeffs[index]]

        # Calculate potfolio statistics
        self.std_array, self.std_err, self.return_matrix = self.calc_std_2D(*input_list)

        # Generate plot
        self.future_plot(
            self.std_array,
            self.std_err,
            self.return_matrix,
            self.months,
            std_mult,
            limit,
            time_index=time_index,
        )

        return

    def plot_securities(self, std_mult=[1, 2, 3], limit=2, time_index=-1):
        # Plot each individual security in the portfolio
        self.perform_task(
            list(self.securities.keys()),
            "plot_individual_securities",
            std_mult=std_mult,
            limit=limit,
            time_index=time_index,
        )
        return

    def fetch_data(self, which="all"):
        # Use data loader to download and clean the latest data
        # Update the data.xlsx sheet with the latest names
        #
        # Note, it is assumed there is already a downloaded version of the security files present
        # but not for the index.

        ## Set the file paths and download urls
        valid_names = self.dataframe["Name"][self.dataframe["Name"].notnull()]
        index_paths = np.empty_like(valid_names)
        index_filename = np.empty_like(index_paths)

        security_paths = np.empty_like(index_paths)
        security_filename = np.empty_like(index_paths)

        # Loop through securities to set up security path and filenames
        for index, filename in enumerate(valid_names):
            # Generating / extracting the index file name and path
            if isinstance(self.dataframe["Index_loc"][index], str):
                index_filename[index] = self.dataframe["Index_loc"][index]
            elif "Nothing" in self.dataframe["Index_down"][index]:
                index_filename[index] = "Nothing"
            else:
                index_filename[index] = filename.replace(" ", "_") + "-yahoo.csv"

            index_paths[index] = os.path.realpath(
                os.path.join(self.folder, "..", "index", index_filename[index])
            )

            # Generating / extracting the index file name and path
            if isinstance(self.dataframe["Security_loc"][index], str):
                sec_file = os.path.splitext(self.dataframe["Security_loc"][index])[0]
            else:
                sec_file = re.search(
                    "fileName.+(?=&)", self.dataframe["Security_down"][index]
                ).group(0)[9:]

            security_filename[index] = (
                sec_file
                + "."
                + re.search("fileType.+(?=&f)", self.dataframe["Security_down"][index]).group(0)[9:]
            )

            security_paths[index] = os.path.join(self.folder, security_filename[index])

            # Changing the ext. to save the security files correctly after having been cleaned
            security_filename[index] = (
                security_filename[index][: security_filename[index].rfind(".")] + ".xlsx"
            )

        if which == "indices" or which == "non-fx" or which == "all":
            # Download the index files
            self.download_indices(self.dataframe["Index_down"], index_paths)

            # Add the new index filenames to the dataframe and save
            self.dataframe["Index_loc"] = index_filename

        if which == "securities" or which == "non-fx" or which == "all":
            # Download the security files (no specific securities wrapper is needed for iShares, they are
            # automatically up-to-date)
            self.perform_download(self.dataframe["Security_down"], security_paths, "Securities")

            # Clean the iShares files
            self.clean_files()

            # Add the new security filenames to the dataframe and save
            self.dataframe["Security_loc"] = security_filename

        if which == "fx" or which == "all":
            print("FX files should be downloaded manually for now.")
            # fx_paths = np.empty_like(self.dataframe["Currency"])
            # fx_filename = np.empty_like(fx_paths)

            # for index, filename in enumerate(self.dataframe["Currency"]):
            #     # Generating / extracting the index file name and path
            #     if isinstance(self.dataframe["Currency_loc"][index], str):
            #         fx_filename[index] = self.dataframe["Currency_loc"][index]
            #     else:
            #         fx_filename[index] = filename.replace(" ", "_") + "-fxtop.csv"

            #     fx_paths[index] = os.path.realpath(
            #         os.path.join(self.folder, "..", "fx", fx_filename[index])
            #     )

            # # Download the security files (no specific securities wrapper is needed for iShares, they are
            # # automatically up-to-date)
            # self.perform_download(self.dataframe["Currency_down"], fx_paths, "FX")

            # # Add the new security filenames to the dataframe and save
            # self.dataframe["Currency_loc"] = fx_filename

        self.save_dataframe()

        return

    def optimise(
        self, loss_type="m+dstd", std_mult=1, months=None, months_weights=None, start_date=None
    ):

        self.calculate_covariance_matrices(months=months, start_date=start_date)

        n_securities = np.shape(self.return_vector.shape)[1]
        n_months = len(months)

        if loss_type == "m+dstd":
            months_weights = np.expand_dims(months_weights, axis=(1, 2))

            cov_signs =  np.sign(self.downside_cov_matrix)
            std_matrix = cov_signs * np.sqrt(np.abs(self.downside_cov_matrix))

            return_vars = months_weights * np.dstack(
                (self.return_vector, std_mult * std_matrix)
            )

            model = self.hedged_performance_loss

            coeff0 = np.full(n_securities, 1.0 / n_securities)  # uniform starting point

            bounds = [(0, 1)] * n_securities
            constraints = [{'type': 'eq', 'fun': lambda c: np.sum(c) - 1}]

            result = minimize(
                model,
                coeff0,
                args=(return_vars,),
                method='trust-constr',
                bounds=bounds,
                constraints=constraints,
            )

            self.coeffs = result.x

            coeff_sqrt = np.sqrt(self.coeffs)
            self.portfolio_downside_std = np.einsum('i, nij, j -> n', coeff_sqrt, return_vars[:, :, 1:], coeff_sqrt)
            self.portfolio_return = np.einsum('i, ni -> n', self.coeffs, return_vars[:, :, 0])

        return result.success

    def hedged_performance_loss(self, return_vars, *args):
        coeffs = np.array(args)
        coeff_sqrt = np.sqrt(coeffs)

        # Variance loss c^T A c for each matrix A
        variance = np.einsum('i, nij, j -> n', coeff_sqrt, return_vars[:, :, 1:], coeff_sqrt)

        # Gain term: c^T b for each vector b
        gain = np.einsum('i, ni -> n', coeffs, return_vars[:, :, 0])

        # Negative gain and positive variance as these are minimized
        # so this way the gain is optimized and variance reduced
        return np.mean(variance) - np.mean(gain)

    def calculate_covariance_matrices(self, months=None, start_date=None):
        # Find the most optimised portfolio, given input on priorities
        securities = self.securities.copy()

        if months is None:
            months = self.months

        (
            tick_intervals,
            market_return_factor,
            market_cov_factor,
            market_downside_cov_factor,
            market_upside_cov_factor,
        ) = self._calculate_market_factor(MARKET_FACTOR_SECURITY, months)

        no_sec = len(securities.keys())
        no_months = len(months)

        self.return_vector = np.empty((no_months, no_sec))
        self.cov_matrix = np.empty((no_months, no_sec, no_sec))
        self.upside_cov_matrix = np.empty_like(self.cov_matrix)
        self.downside_cov_matrix = np.empty_like(self.cov_matrix)
        self.start_tick_matrix = np.empty((no_sec, no_sec))
        self.end_tick_matrix = np.empty_like(self.start_tick_matrix)

        # Calculate factors per security (no cross-terms yet)
        for index, (key, security) in enumerate(securities.items()):
            print(key)
            if start_date is not None:
                _, tick_time, return_series = security._set_start_tick(start_date)
            else:
                start_tick = security.tick_time[0]
                tick_time = security.tick_time.copy()
                return_series = security.return_series.copy()

            return_mx = security.calc_return_matrix(
                months=months, tick_time=tick_time, return_series=return_series
            )

            # Find the relevant market-correction factor
            market_factor_index = np.argmin(np.abs(tick_intervals - start_tick))

            (
                return_value,
                cov_value,
                downside_cov_value,
                upside_cov_value,
                _,
                _,
            ) = self.calc_cov(return_mx)

            self.return_vector[:, index] = (
                return_value[:, 0, 0] / market_return_factor[:, market_factor_index]
            )
            self.cov_matrix[:, index, index] = (
                cov_value[:, 0, 0] / market_cov_factor[:, market_factor_index]
            )
            self.downside_cov_matrix[:, index, index] = (
                downside_cov_value[:, 0, 0] / market_downside_cov_factor[:, market_factor_index]
            )
            self.upside_cov_matrix[:, index, index] = (
                upside_cov_value[:, 0, 0] / market_upside_cov_factor[:, market_factor_index]
            )

            self.start_tick_matrix[index, index] = start_tick
            self.end_tick_matrix[index, index] = security.tick_time[-1]

        security_keys = list(securities.keys())

        # Calculate all the cross-terms
        for index, (key, security) in enumerate(securities.items()):
            print(key)
            if start_date is not None:
                start_tick, tick_time, return_series = security._set_start_tick(start_date)
            else:
                start_tick = security.tick_time[0]
                tick_time = security.tick_time.copy()
                return_series = security.return_series.copy()

            del security_keys[0]

            for i, sub_key in enumerate(security_keys):
                print("sub key: ", sub_key, index, i)
                sub_security = securities[sub_key]
                sub_index = index + i + 1

                sub_start_tick = max(start_tick, sub_security.tick_time[0])
                sub_end_tick = min(tick_time[-1], sub_security.tick_time[-1])

                # Slice main security
                start_index = np.argmin(np.abs(tick_time - sub_start_tick))
                end_index = np.argmin(np.abs(tick_time - sub_end_tick))
                sub_tick_time = tick_time[start_index:end_index]
                sub_return_series = return_series[start_index:end_index]

                # Slice other security
                start_index = np.argmin(np.abs(sub_security.tick_time - sub_start_tick))
                end_index = np.argmin(np.abs(sub_security.tick_time - sub_end_tick))
                other_sec_tick_time = sub_security.tick_time[start_index:end_index]
                other_sec_return_series = sub_security.return_series[start_index:end_index]

                if len(sub_tick_time) != len(other_sec_tick_time):
                    raise ValueError(
                        f"Tick time lengths are not equal for '{key}' and '{sub_key}': "
                        f"{len(sub_tick_time)} != {len(other_sec_tick_time)}"
                    )

                sub_return_mx = security.calc_return_matrix(
                    months=months, tick_time=sub_tick_time, return_series=sub_return_series
                )
                other_return_mx = sub_security.calc_return_matrix(
                    months=months,
                    tick_time=other_sec_tick_time,
                    return_series=other_sec_return_series,
                )

                _, cov_value, downside_cov_value, upside_cov_value, _, _ = self.calc_cov(
                    sub_return_mx, other_return_mx
                )

                cov_corr_factor = (self.cov_matrix[:, index, index] / cov_value[:, 0, 0]) * (
                    self.cov_matrix[:, sub_index, sub_index] / cov_value[:, -1, -1]
                )
                downside_cov_corr_factor = (
                    self.downside_cov_matrix[:, index, index] / downside_cov_value[:, 0, 0]
                ) * (
                    self.downside_cov_matrix[:, sub_index, sub_index]
                    / downside_cov_value[:, -1, -1]
                )
                upside_cov_corr_factor = (
                    self.upside_cov_matrix[:, index, index] / upside_cov_value[:, 0, 0]
                ) * (self.upside_cov_matrix[:, sub_index, sub_index] / upside_cov_value[:, -1, -1])

                self.cov_matrix[:, index, sub_index] = cov_value[:, 0, -1] / np.sqrt(
                    cov_corr_factor
                )
                self.downside_cov_matrix[:, index, sub_index] = cov_value[:, 0, -1] / np.sqrt(
                    downside_cov_corr_factor
                )
                self.upside_cov_matrix[:, index, sub_index] = cov_value[:, 0, -1] / np.sqrt(
                    upside_cov_corr_factor
                )

                self.start_tick_matrix[index, sub_index] = sub_start_tick
                self.end_tick_matrix[index, sub_index] = sub_end_tick

        # Mirror the upper triangle into the lower triangle for all covariance matrices
        self.cov_matrix = self.mirror_array_of_matrices_around_diagonal(self.cov_matrix)
        self.downside_cov_matrix = self.mirror_array_of_matrices_around_diagonal(
            self.downside_cov_matrix
        )
        self.upside_cov_matrix = self.mirror_array_of_matrices_around_diagonal(
            self.upside_cov_matrix
        )
        self.start_tick_matrix = (
            np.triu(self.start_tick_matrix) + np.triu(self.start_tick_matrix, k=1).T
        )
        self.end_tick_matrix = np.triu(self.end_tick_matrix) + np.triu(self.end_tick_matrix, k=1).T

        return

    def save_dataframe(
        self,
        data_location=os.path.realpath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "data", "data.xlsx")
        ),
    ):
        # Used to save the updated dataframe to the data.xlsx file
        self.dataframe.to_excel(data_location, index=False)

        return

    ## Secondary functions:
    def _calculate_market_factor(self, market_security_wildcard, months):
        """Returns market scaling factors for return parameters based on data intervals"""
        matches = [
            key
            for key in self.securities.keys()
            if fnmatch.fnmatchcase(key, market_security_wildcard)
        ]

        if len(matches) == 0:
            raise KeyError(f"No security matched wildcard '{market_security_wildcard}'.")
        if len(matches) > 1:
            raise ValueError(
                f"Multiple securities matched wildcard '{market_security_wildcard}': {matches}"
            )

        sec = self.securities[matches[0]]

        tick_intervals = np.arange(
            sec.tick_time[0], sec.tick_time[-1] - np.max(months) * STANDARD_MONTH_SIZE, 180
        )
        # Assign empty array (note, 8 is for the 8 different elements in the calc_std_1D output)
        return_vector = np.empty((len(months), len(tick_intervals)))
        cov_matrix = np.empty_like(return_vector)
        downside_cov_matrix = np.empty_like(return_vector)
        upside_cov_matrix = np.empty_like(return_vector)
        start_indices = np.asarray(tick_intervals - tick_intervals[0], dtype=int)

        for ind, start_index in enumerate(start_indices):
            tick_time = sec.tick_time[start_index:]
            return_series = sec.return_series[start_index:]

            return_mx = sec.calc_return_matrix(
                months=months, tick_time=tick_time, return_series=return_series
            )

            # Calculate statistics
            (
                return_value,
                cov_value,
                downside_cov_value,
                upside_cov_value,
                _,
                _,
            ) = sec.calc_cov(return_mx)

            return_vector[:, ind] = return_value[:, 0, 0]
            cov_matrix[:, ind] = cov_value[:, 0, 0]
            downside_cov_matrix[:, ind] = downside_cov_value[:, 0, 0]
            upside_cov_matrix[:, ind] = upside_cov_value[:, 0, 0]

        # Normalise to the full length market data (at ind = 0).
        # This factor now provides a factor
        return_vector /= return_vector[:, 0:1]
        cov_matrix /= cov_matrix[:, 0:1]
        downside_cov_matrix /= downside_cov_matrix[:, 0:1]
        upside_cov_matrix /= upside_cov_matrix[:, 0:1]

        return tick_intervals, return_vector, cov_matrix, downside_cov_matrix, upside_cov_matrix

    def load_securities(self, security_name, load=False, fx_df=None):

        index = self.dataframe["Name"][self.dataframe["Name"] == security_name].index[0]
        if self.dataframe["Used"][index] == 0:
            print(f"\n{security_name} is not used in the portfolio, skipping...")
            return

        if (
            not isinstance(self.dataframe["Security_loc"][index], str)
            or self.dataframe["Security_loc"][index] == ""
        ):
            print(f"\nNo security location defined for {security_name}, skipping...")
        else:
            if load == False:
                sec_filepath = os.path.join(self.folder, self.dataframe["Security_loc"][index])
                dist_fund = self.dataframe["Dist_fund"][index] == 1

                if isinstance(self.dataframe["Index_loc"][index], str):
                    index_filepath = os.path.join(
                        self.folder, "..", "index", self.dataframe["Index_loc"][index]
                    )
                    sec = Security(
                        sec_filepath,
                        index_filepath,
                        dist_fund=dist_fund,
                        fx_df=fx_df,
                        calc_mat=False,
                        name=security_name,
                    )
                else:
                    sec = Security(
                        sec_filepath,
                        dist_fund=dist_fund,
                        fx_df=fx_df,
                        calc_mat=False,
                        name=security_name,
                    )

                # Create the entry in the dataframe based on the security name directly, rather than its name
                # in the Excel data sheet
                self.securities[sec.name] = sec

            else:
                # Generate pickle file filename. Generated in the same way as when it is saved.
                # This only works if the names in the data.xlsx file correspond with the pickle file names
                pickle_path = os.path.join(
                    self.folder, "..", "pickles", security_name.replace(" ", "_") + ".pkl"
                )

                # Loading the pickle file. Note, as it had been created before the data.xlsx name should be correct
                with open(pickle_path, "rb") as file:
                    self.securities[security_name] = pickle.load(file)

        return

    def calc_return_matrix_per_security(self, name, **kwargs):
        self.securities[name].return_matrix = self.securities[name].calc_return_matrix(**kwargs)
        return

    def plot_individual_securities(self, name, **kwargs):
        self.securities[name].plot_security(**kwargs)
        return
