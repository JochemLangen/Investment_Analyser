import datetime as dt
import matplotlib.pyplot as plt
import numpy as np
from os.path import realpath

# from scipy.stats import norm
import scipy.stats
from investment_analyser.stats import Stats
from investment_analyser.backtrace import DEFAULT_SMOOTHENING_RANGE


class Plotter(Stats):
    script_location = realpath(__file__)

    def __init__(self, fontsize=15, tickwidth=2, ticklength=4):
        self.fontsize = fontsize
        self.tickwidth = tickwidth
        self.ticklength = ticklength
        return

    def future_plot(
        self, std_array, std_err, return_mat, time, title_input, std_mult, limit_mult, time_index=-1
    ):

        std_mult = np.asarray(std_mult)

        # Create figure with appropriate size
        fig = plt.figure(figsize=(16, 10))

        # Cumulative return
        ax1 = fig.add_axes([0.1, 0.55, 0.45, 0.35])
        plt.title(title_input, fontsize=self.fontsize, loc="left")

        ax1 = self.__generate_plot(
            ax1,
            std_array,
            std_err,
            time,
            std_mult,
            limit_mult,
            ylabel="Cum. Relative Return (%)",
            xlabel=None,
        )

        # Annual return
        ax2 = fig.add_axes([0.1, 0.1, 0.45, 0.35])
        ax2 = self.__generate_plot(
            ax2,
            std_array[:, 4:],
            std_err[:, 4:],
            time,
            std_mult,
            limit_mult,
            ylabel="Avg. Annualised Relative Return (%)",
        )
        plt.title(
            f"Avg. Annualised Relative Return at {time[time_index]} months: {round(std_array[time_index, 4], 2)}%",
            fontsize=self.fontsize,
        )

        # Distribution plot
        ax3 = fig.add_axes([0.65, 0.1, 0.3, 0.8])
        ax3 = self.__distr_plot(ax3, return_mat, std_mult, time, time_index)
        plt.show()
        return

    def historic_plot(
        self, return_series, tick_time, orig_tick_time,
        index_return_series, index_tick_time, orig_index_tick_time,
        security_start_tick, backtrace_factor_series, backtrace_series, backtrace_params, title_input,
    ):
        # Take only the values of the return series that correspond to the original tick time
        orig_return_series = return_series[np.isin(tick_time, orig_tick_time)]
        orig_return_series = orig_return_series / orig_return_series[0] * 100

        if len(index_return_series) > 0:
            orig_index_return_series = index_return_series[np.isin(index_tick_time, orig_index_tick_time)]
            valid_index_ticks = orig_index_tick_time >= orig_tick_time[0]

            orig_index_tick_time = orig_index_tick_time[valid_index_ticks]
            orig_index_return_series = orig_index_return_series[valid_index_ticks]
            orig_index_return_series = orig_index_return_series / orig_index_return_series[0] * 100

        # Determine the average annual return over the entire period
        year_diff = (orig_tick_time[-1] - orig_tick_time[0])/365.25
        avg_annual_return = ((orig_return_series[-1]/100)**(1/year_diff) - 1)*100

        # Format tick time back to datetime format
        t = self.revert_timeseries_back(orig_tick_time)
        t_index = self.revert_timeseries_back(orig_index_tick_time)
        t_inception = self.revert_timeseries_back(security_start_tick)

        # Create figure with appropriate size
        fig = plt.figure(figsize=(16, 10))

        # Cumulative return
        ax = fig.add_axes([0.1, 0.60, 0.8, 0.35])
        ax.text(
            0.5,
            0.98,
            f"Avg. annual return: {avg_annual_return:.2f}%",
            ha="center",
            va="top",
            fontsize=self.fontsize-3,
            transform=ax.transAxes,
        )
        plt.title(title_input, fontsize=self.fontsize, loc="left")

        lim_max = max(orig_return_series)
        lim_min = min(max([0, min(orig_return_series)]),100)

        ax.plot([t[0], t[-1]], [orig_return_series[0], orig_return_series[-1]], color="gray", linestyle=":", label=f"{avg_annual_return:.2f}% annual return")
        t_str_inception = dt.datetime.utcfromtimestamp(int(np.round(t_inception[0]))).strftime("%Y/%m/%d")
        ax.plot([t_inception, t_inception], [lim_min, lim_max], color="red", linestyle="--", label=f"Security Inception: {t_str_inception}")
        if len(index_return_series) > 0:
            ax.plot(t_index, orig_index_return_series, color="green", label="Raw Index")
        ax.plot(t, orig_return_series, color="black", label="Index (incl. dividends) + Security")

        plt.legend()
        plt.ylim([lim_min, lim_max])
        plt.xlim([t[0], t[-1]])
        plt.yscale("log")

        plt.ylabel("Return (%)", fontsize=self.fontsize)

        self._set_ticks(ax, t)

        # Second plot
        if len(backtrace_factor_series) > 0:
            # Also normalise this to one, this does not necessarily need to start at one,
            # but the index and security data above have also been normalised, so this data should match
            backtrace_factor_series = backtrace_factor_series/ backtrace_factor_series[0]

            t_index_full = self.revert_timeseries_back(index_tick_time[1:])

            ax2 = fig.add_axes([0.1, 0.1, 0.35, 0.35])
            ax2.plot(t_index_full, backtrace_factor_series, color="blue", linestyle="--", label="Backtrace Model")
            plt.title("Backtracing conversion factor from index to security", fontsize=self.fontsize, loc="left")

            lim_max = max(backtrace_factor_series)
            lim_min = min([1, min(backtrace_factor_series)])
            plt.ylim([lim_min, lim_max])
            plt.xlim([t_index_full[0], t_index_full[-1]])

            plt.ylabel("Factor", fontsize=self.fontsize)

            self._set_ticks(ax2, t_index_full)

            # Add backtrace fitting statistics text
            if backtrace_params:
                backtrace_text_lines = []
                backtrace_text_lines.append(f"Model type: {backtrace_params.get('Model type', 'N/A')}")
                backtrace_text_lines.append(f"Condition no. mag: {backtrace_params.get('Condition no. mag', 'N/A'):.2f}")
                backtrace_text_lines.append(f"R_adj²: {backtrace_params.get('R_adj^2', 'N/A'):.4f}")
                backtrace_text_lines.append(f"Durbin-Watson: {backtrace_params.get('Durbin-Watson', 'N/A'):.4f}")

                if "Exp-trig corr" in backtrace_params:
                    backtrace_text_lines.append(f"Exp-trig corr: {backtrace_params['Exp-trig corr']:.4f}")
                if "Exp-trig orth" in backtrace_params:
                    backtrace_text_lines.append(f"Exp-trig orth: {backtrace_params['Exp-trig orth']:.4f}")
                if "Max exp_trig orth" in backtrace_params:
                    backtrace_text_lines.append(f"Max exp_trig orth: {backtrace_params['Max exp_trig orth']:.4f}")

                backtrace_text = "\n".join(backtrace_text_lines)
                ax2.text(
                    0.02,
                    0.98,
                    backtrace_text,
                    ha="left",
                    va="top",
                    fontsize=self.fontsize-3,
                    transform=ax2.transAxes,
                    family="monospace",
                    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
                )

        # Plot 3
        if len(index_return_series) > 0 and len(backtrace_series) > 0:
            valid_index_ticks = index_tick_time[1:] >= (security_start_tick + DEFAULT_SMOOTHENING_RANGE)
            backtrace_series = backtrace_series[valid_index_ticks]
            backtrace_series = backtrace_series / backtrace_series[0] * 100

            index_return_series = index_return_series[1:][valid_index_ticks]
            index_return_series = index_return_series / index_return_series[0] * 100

            t_fit_index = index_tick_time[1:][valid_index_ticks]

            valid_ticks = tick_time >= (security_start_tick + DEFAULT_SMOOTHENING_RANGE)
            return_series = return_series[valid_ticks]
            return_series = return_series / return_series[0] * 100

            t_fit = tick_time[valid_ticks]

            # Determine the average annual return over the entire period
            year_diff = (t_fit[-1] - t_fit[0])/365.25
            avg_annual_return = ((return_series[-1]/100)**(1/year_diff) - 1)*100

            t_fit = self.revert_timeseries_back(t_fit)
            t_fit_index = self.revert_timeseries_back(t_fit_index)

            ax3 = fig.add_axes([0.55, 0.1, 0.35, 0.35])
            ax3.plot([t_fit[0], t_fit[-1]], [return_series[0], return_series[-1]], color="gray", linestyle=":", label=f"{avg_annual_return:.2f}% annual return")
            ax3.plot(t_fit_index, index_return_series, color="green", label="Raw Index")
            ax3.plot(t_fit_index, backtrace_series, color="orange", label="Scaled Index")
            ax3.plot(t_fit, return_series, color="black", label="Security")
            plt.title(f"Historic series backtracing fit for security ({t_str_inception}+)", fontsize=self.fontsize, loc="left")

            lim_max = max(return_series)
            lim_min = min(index_return_series)
            plt.ylim([lim_min, lim_max])
            plt.xlim([t_fit[0], t_fit[-1]])

            plt.yscale("log")
            plt.ylabel("Return (%)", fontsize=self.fontsize)
            plt.legend(loc="upper left")

            self._set_ticks(ax3, t_fit)

        plt.show()
        return

    def revert_timeseries_back(self, tick_time):
        return (tick_time - self.convert_time(
            np.array(["01/Jan/1970"]), time_form="iShares"
        )) * 86400


    def __generate_plot(
        self,
        ax,
        std_array,
        std_err,
        time,
        std_mult,
        limit_mult,
        scale=None,
        ylabel="Return (%)",
        xlabel="Time (months)",
    ):

        ax.plot(time, np.zeros_like(time), color="gray", linestyle=":")
        colour_base = 0.3
        colours = (1 - colour_base) * std_mult / max(std_mult)
        colour_max_i = len(colours) - 1

        # Positive std lines
        for index, stdi in enumerate(std_mult[::-1]):
            pos_colour = [0, colours[colour_max_i - index], colours[colour_max_i - index]]
            ax.errorbar(
                time,
                std_array[:, 0] + stdi * std_array[:, 3],
                yerr=np.sqrt(std_err[:, 0] ** 2 + (stdi * std_err[:, 3]) ** 2),
                linestyle="--",
                color=pos_colour,
                marker="x",
                label=f"m + {stdi}s",
            )
        # Main line
        ax.errorbar(
            time, std_array[:, 0], yerr=std_err[:, 0], color="black", marker="x", label="mean"
        )

        # Negative std lines
        for index, stdi in enumerate(std_mult):
            neg_colour = [colours[index], 0, colours[index]]
            ax.errorbar(
                time,
                std_array[:, 0] - stdi * std_array[:, 2],
                yerr=np.sqrt(std_err[:, 0] ** 2 + (stdi * std_err[:, 2]) ** 2),
                linestyle="--",
                color=neg_colour,
                marker="x",
                label=f"m - {stdi}s",
            )

        ax.legend()
        lim_max = max(std_array[:, 0] + limit_mult * std_array[:, 3])
        lim_min = max([-100, min(std_array[:, 0] - limit_mult * std_array[:, 2])])
        plt.ylim([lim_min, lim_max])
        plt.xlim([time[0], time[-1]])
        if scale == "log":
            plt.xscale("log")

        plt.ylabel(ylabel, fontsize=self.fontsize)

        ax.tick_params(left=True, right=True, labelleft=True, labelright=True)
        plt.yticks(fontsize=self.fontsize)
        plt.tick_params(axis="both", which="major", width=self.tickwidth, length=self.ticklength)
        plt.minorticks_on()
        plt.tick_params(
            axis="both", which="minor", width=self.tickwidth * 2 / 3, length=self.ticklength / 2
        )
        plt.tick_params(axis="both", which="both", left=True, right=True)

        if xlabel == None:
            ax.xaxis.tick_top()
        else:
            plt.xlabel(xlabel, fontsize=self.fontsize)

        plt.xticks(fontsize=self.fontsize)

        return ax

    def __distr_plot(self, ax, y_mat, std_mult, time, time_index):

        y_series = np.sort(y_mat[time_index])
        y_series = y_series[~np.isnan(y_series)]
        y_len = len(y_series)

        y_mean = np.mean(y_series)

        n_elem = np.shape(y_series)[0]

        downside_var = 2 * np.nanmean(np.square(np.maximum(0, y_mean - y_series))) * n_elem / (n_elem - 1)
        upside_var = 2 * np.nanmean(np.square(np.maximum(0, y_series - y_mean))) * n_elem / (n_elem - 1)
        downside_std = np.sqrt(downside_var)
        upside_std = np.sqrt(upside_var)
        y_std = np.append([upside_std]*(len(std_mult)+1),[downside_std]*len(std_mult))

        # Plot the histogram
        # The Freedman-Diaconis rule is used to obtain the bin width:
        # Note, assumption of using int works approx for y_len being large enough,
        # Otherwise, interpolation between points should be used
        inter_qrt_range = y_series[int(y_len * 3 / 4)] - y_series[int(y_len / 4)]
        bin_width = 2 * inter_qrt_range / np.cbrt(y_len)
        abs_max = np.max(abs(y_series - y_mean)) + bin_width
        bin_lim = np.array([y_mean - abs_max, y_mean + abs_max])
        bin_no = int(2 * abs_max / bin_width)

        ax.hist(y_series, bins=bin_no, range=[bin_lim[0], bin_lim[1]], density=True, zorder=30)

        # Plot probability lines
        ylimits = ax.get_ylim()
        std_mult_arr = np.append(np.append(std_mult[::-1], 0), -std_mult)
        txt_y_pos = ylimits[1]
        ylim = [ylimits[0], ylimits[1] * 11 / 10]  # To provide space for the text

        for index, stdi in enumerate(std_mult_arr):
            x_pos = y_mean + stdi * y_std[index]
            ax.plot([x_pos, x_pos], ylim, linestyle=":", color="black", zorder=index)

            # Print corresponding percentage
            nearest_index = np.argmin(abs(y_series - x_pos))
            if y_series[nearest_index] > x_pos:  # Looking at percentage of points included below,
                # so if the value is below the nearest index point, it will be one lower
                # y_len is already +1 compared to the indices so for val < x_pos, nothing is added
                percentage = np.round((nearest_index + 1) / y_len * 100, decimals=1)
            else:
                percentage = np.round(nearest_index / y_len * 100, decimals=1)

            if stdi < 0:
                plt.text(
                    x_pos + bin_width / 2,
                    txt_y_pos,
                    f"m - {-stdi}s\n={percentage}%",
                    zorder=32,
                )
            elif stdi > 0:
                plt.text(
                    x_pos + bin_width / 2,
                    txt_y_pos,
                    f"m + {stdi}s\n={percentage}%",
                    zorder=32,
                )
            else:
                plt.text(
                    x_pos + bin_width / 2, txt_y_pos, f"mean\n={percentage}%", zorder=32
                )

        # Plot normal distr.
        xlimits = ax.get_xlim()
        return_arr = np.linspace(xlimits[0], y_mean, 60)
        prob_arr = scipy.stats.truncnorm.pdf(
            return_arr, (-100 - y_mean) / downside_std, np.inf, loc=y_mean, scale=downside_std
        )

        ax.plot(return_arr, prob_arr, linestyle="--", color="black", zorder=31)

        return_arr = np.linspace(y_mean, xlimits[1], 60)
        prob_arr = scipy.stats.truncnorm.pdf(
            return_arr, (-100 - y_mean) / upside_std, np.inf, loc=y_mean, scale=upside_std
        )

        ax.plot(return_arr, prob_arr, linestyle="--", color="black", zorder=31)

        if y_mean + (std_mult[-1] + 1) * upside_std > bin_lim[1]:
            plt.xlim(
                [y_mean - std_mult[-1] * downside_std - bin_width, y_mean + (std_mult[-1] + 1) * upside_std]
            )  # Extra space because of text
        else:
            plt.xlim(bin_lim)

        plt.ylim(ylim)
        plt.ylabel("Normalised Probability Density", fontsize=self.fontsize)
        plt.xlabel("Cumulative Relative Return (%)", fontsize=self.fontsize)
        ax.yaxis.set_label_position("right")

        ax.tick_params(which="both", left=False, right=True, labelleft=False, labelright=True)
        ax.tick_params(axis="both", which="major", width=self.tickwidth, length=self.ticklength)
        ax.minorticks_on()
        ax.tick_params(
            axis="both", which="minor", width=self.tickwidth * 2 / 3, length=self.ticklength / 2
        )
        plt.xticks(fontsize=self.fontsize)
        plt.yticks(fontsize=self.fontsize)
        plt.title(
            f"Return distribution at {time[time_index]} months", fontsize=self.fontsize
        )

        return ax
    
    def _set_ticks(self, ax, t):
        ax.tick_params(left=True, right=True, labelleft=True, labelright=True)
        plt.yticks(fontsize=self.fontsize)
        plt.tick_params(axis="both", which="major", width=self.tickwidth, length=self.ticklength)
        plt.minorticks_on()
        plt.tick_params(
            axis="both", which="minor", width=self.tickwidth * 2 / 3, length=self.ticklength / 2
        )
        plt.tick_params(axis="both", which="both", left=True, right=True)

        plt.xlabel("Date", fontsize=self.fontsize)

        xtick_positions = ax.get_xticks()
        if len(xtick_positions) > 0:
            xtick_labels = [
                dt.datetime.utcfromtimestamp(int(np.round(x))).strftime("%Y/%m/%d")
                for x in xtick_positions
            ]
            ax.set_xticks(xtick_positions)
            ax.set_xticklabels(xtick_labels, fontsize=self.fontsize-3, rotation=45, ha="right")
            plt.xlim([t[0], t[-1]])
        return

    def full_plot(self):
        # Will also include historic data of the portfolio
        return

    def plot_backtracing(
        self,
    ):
        ## Plotting
        offset = 0
        range_lim = [offset + 14500, offset + 16000]

        fig = plt.figure()
        # plt.plot(t_old, y_old, label='index')
        plt.plot(
            new_t[range_lim[0] : range_lim[1]],
            fitted_y[range_lim[0] : range_lim[1]],
            label="fitted",
        )
        # plt.plot(t_old, fitted_y, label='fitted')

        plt.plot(t[offset : offset + 1300], y[offset : offset + 1300], label="orig")
        plt.plot(
            new_t[range_lim[0] : range_lim[1]],
            smooth_y[range_lim[0] : range_lim[1]],
            label="final data",
        )
        plt.legend()
        plt.show()

        fig = plt.figure()
        # plt.plot(t_old, y_old, label='index')
        plt.plot(t_old[:-1][-y_len:], fitted_y[-y_len:], label="fitted")
        # plt.plot(t_old, fitted_y, label='fitted')

        plt.plot(t, y, label="orig")
        plt.yscale("log")
        plt.legend()
        plt.show()

        plt.figure()
        plt.plot(t_old[1:], (fitted_y / y_n_factor) / (y_old[1:] / y_old_n_factor))
        plt.show()

        plt.figure()
        plt.plot(t_old[1:], fitted_y)
        plt.plot(t_old[1:], y_old[1:] / y_old_n_factor * y_n_factor)
        plt.plot(t, y, label="orig")
        plt.yscale("log")
        plt.show()

        plt.figure()
        plt.scatter(y_old_norm[1:], fitted_y[-y_len:] / y_n_factor, marker=".")
        plt.scatter(y_old_norm[1:], y_norm, marker=".")
        plt.ylabel("Y norm")
        plt.xlabel("Y index norm")
        plt.show()

        plt.figure()
        plt.plot(t, y_resid / y)
        plt.ylim([-0.1, 0.1])
        plt.show()

        return
