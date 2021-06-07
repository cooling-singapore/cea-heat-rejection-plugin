from os import path

import matplotlib.pyplot as plt

from cea_heat_rejection_plugin.utilities.DK_thermo import getstate
from cea_heat_rejection_plugin.utilities.coolingtowers import PathProj

PathPlots = path.join(PathProj, 'Results', 'Plots')


def plt_AmbientAirPerformance_exhaust(state, results, Tin, RH_values, pu_load, pump_ctrl, plot_setpoint=False,
                                      save_as=None, **kwargs):
    """Plots the ambient air performance -- exhaust air state vs. T ambient

    This plots the target variable vs T ambient parametrized by RH.

    Parameters:
        state           State of humidair (currently support: TDryBulb and HumRatio)

        results         Dict of {pump_ctrl, RH, *: val}, where * are the standard keys in simulate_CT(); and val
                        are the results objects returned.

        Tin             The sequence of ambient air temperatures [°C] (independent variable)

        RH_values       The sequence of relative humidity values [0,1]

        pu_load         CT load in per unit [0,1]

        pump_ctrl       Boolean flag for pump control (part of results key)

        plot_setpoint   (Optional; defaults to False). Plots the set-point exhaust state according to the designed
                        value. This is a constant T- and w-line. If True, then need to provide the ff. kwargs:
                        'T_sp' and 'w_sp' as the temperature and relative humidity set points,
                        respectively.


        kwargs          Plot kwargs
    """
    def_ylabels = {
        'TDryBulb': 'Temp (dry bulb) [°C]',
        'HumRatio': '[kg vapor/kg d.a.]',
    }
    def_titles = {
        'TDryBulb': 'Dry Bulb Temperature',
        'HumRatio': 'Humidity Ratio',
        1: 'Full',
        0: 'No',
    }
    def_kwargs = {
        'title': 'Exhaust {} at {} Load'.format(def_titles.get(state, '*'),
                                                def_titles.get(pu_load, '{:0.1f}%'.format(pu_load * 100))),
        'ylabel': '{}'.format(def_ylabels.get(state, '*')),
        'xlabel': 'Ambient Temp (dry bulb) [°C]',
        'setpoint_line': {'ls': '--', 'lw': 1, 'color': 'k'},
    }

    kwargs.update({key: val for key, val in def_kwargs.items() if key not in kwargs})
    kwargs.update({key: val for key, val in common_def_kwargs.items() if key not in kwargs})

    RH_color_seq = ('#2E86C1', '#16A085', '#D35400')

    # ----------------------------------------------------- PLOT
    plt.figure(figsize=kwargs['figsize'])
    for idx, RH in enumerate(RH_values):
        plt.plot(Tin, getstate(state, results[pump_ctrl, RH, 'air_o']),
                 label='{:0.2f} RH'.format(RH), color=RH_color_seq[idx])

    ax = plt.gca()
    # ax = basic_plot_polishing(ax, **kwargs)

    if plot_setpoint:
        setpoint = kwargs[{'TDryBulb': 'T_sp', 'HumRatio': 'w_sp'}[state]]
        ax.axhline(setpoint, **kwargs['setpoint_line'])

        # Text label
        y_lb, y_ub = ax.get_ylim()
        text_y = setpoint + 0.03 * (y_ub - y_lb)
        if text_y > y_ub * 0.95: text_y = setpoint - 0.03 * (y_ub - y_lb)

        plt.text(Tin.min(), text_y, 'set point')

    if save_as:
        plt.savefig(path.join(PathPlots, save_as), dpi=kwargs.get('dpi'))

    plt.show()
    return


def plt_AmbientAirPerformance_airflow(results, Tin, RH_values, pu_load, pump_ctrl, plot_setpoint=True, save_as=None,
                                      **kwargs):
    """Plots the ambient air performance -- air flow vs. T ambient"""
    def_kwargs = {
        'title': 'Air Mass Flow at {} Load'.format({1: 'Full', 0: 'No'}.get(pu_load, '{:0.1f}%'.format(pu_load * 100))),
        'ylabel': '[kg/s]',
        'xlabel': 'Temp (dry bulb) [°C]',
        'setpoint_line': {'ls': '--', 'lw': 1, 'color': 'k'},
    }
    kwargs.update({key: val for key, val in def_kwargs.items() if key not in kwargs})
    kwargs.update({key: val for key, val in common_def_kwargs.items() if key not in kwargs})

    RH_color_seq = ('#2E86C1', '#16A085', '#D35400')

    # ----------------------------------------------------- PLOT
    plt.figure(figsize=kwargs['figsize'])

    for idx, RH in enumerate(RH_values):
        plt.plot(Tin, results[pump_ctrl, RH, 'air flow'].magnitude,
                 label='{:0.2f} RH'.format(RH), color=RH_color_seq[idx])

    ax = plt.gca()
    # ax = basic_plot_polishing(ax, **kwargs)

    if plot_setpoint:
        setpoint = kwargs['airflow_sp']
        ax.axhline(setpoint, **kwargs['setpoint_line'])

        # Text label
        y_lb, y_ub = ax.get_ylim()
        text_y = setpoint + 0.03 * (y_ub - y_lb)
        if text_y > y_ub * 0.95: text_y = setpoint - 0.03 * (y_ub - y_lb)

        plt.text(Tin.min(), text_y, 'nominal')

    if save_as:
        plt.savefig(path.join(PathPlots, save_as), dpi=kwargs.get('dpi'))

    plt.show()
    return


def plt_LoadingPerformance_exhaust(state, results, CT_load, air_i, pump_ctrl, plot_setpoint=True, save_as=None,
                                   **kwargs):
    """Plots the loading performance -- exhaust vs. load kW"""
    def_ylabels = {
        'TDryBulb': 'Temp (dry bulb) [°C]',
        'HumRatio': '[kg vapor/kg d.a.]',
    }
    def_titles = {
        'TDryBulb': 'Temperature',
        'HumRatio': 'Humidity Ratio',
    }
    def_kwargs = {
        'xlabel': 'heat load [kW]',
        'ylabel': '{}'.format(def_ylabels.get(state, '*')),
        'title': 'Exhaust {} vs. Load'.format(def_titles.get(state, '*')),
        'setpoint_line': {'ls': '--', 'lw': 1, 'color': 'k'},
    }
    kwargs.update({key: val for key, val in def_kwargs.items() if key not in kwargs})
    kwargs.update({key: val for key, val in common_def_kwargs.items() if key not in kwargs})

    RH_color_seq = ('#2E86C1', '#16A085', '#D35400')

    # ----------------------------------------------------- PLOT
    plt.figure(figsize=kwargs['figsize'])

    for idx, _air_i in enumerate(air_i):
        _T, _RH = _air_i.TDryBulb, _air_i.RelHum
        plt.plot(CT_load.magnitude, getstate(state, results[_T, _RH, pump_ctrl, 'air_o']),
                 label='{:0.1f}°C, {:0.3f} RH'.format(_T, _RH), color=RH_color_seq[idx])

    ax = plt.gca()

    # ax = basic_plot_polishing(ax, **kwargs)

    if plot_setpoint:
        setpoint = kwargs[{'TDryBulb': 'T_sp', 'HumRatio': 'w_sp'}[state]]
        ax.axhline(setpoint, **kwargs['setpoint_line'])

        # Text label
        y_lb, y_ub = ax.get_ylim()
        text_y = setpoint + 0.03 * (y_ub - y_lb)
        if text_y > y_ub * 0.95: text_y = setpoint - 0.03 * (y_ub - y_lb)

        plt.text(0, text_y, 'set point')

    if save_as:
        plt.savefig(path.join(PathPlots, save_as), dpi=kwargs.get('dpi'))

    plt.show()
    return


def plt_LoadingPerformance_airflow(results, CT_load, air_i, pump_ctrl, plot_setpoint=True, save_as=None, **kwargs):
    """Plots the loading performance -- air flow vs. load kW"""
    def_kwargs = {
        'xlabel': 'heat load [kW]',
        'ylabel': '[kg/s]',
        'title': 'Air Mass Flow vs. Load',
        'setpoint_line': {'ls': '--', 'lw': 1, 'color': 'k'},
    }
    kwargs.update({key: val for key, val in def_kwargs.items() if key not in kwargs})
    kwargs.update({key: val for key, val in common_def_kwargs.items() if key not in kwargs})

    RH_color_seq = ('#2E86C1', '#16A085', '#D35400')

    # ----------------------------------------------------- PLOT
    plt.figure(figsize=kwargs['figsize'])

    for idx, _air_i in enumerate(air_i):
        _T, _RH = _air_i.TDryBulb, _air_i.RelHum
        plt.plot(CT_load.magnitude, results[_T, _RH, pump_ctrl, 'air flow'].magnitude,
                 label='{:0.1f}°C, {:0.3f} RH'.format(_T, _RH), color=RH_color_seq[idx])

    ax = plt.gca()
    # ax = basic_plot_polishing(ax, **kwargs)

    if plot_setpoint:
        setpoint = kwargs['airflow_sp']
        ax.axhline(setpoint, **kwargs['setpoint_line'])

        # Text label
        y_lb, y_ub = ax.get_ylim()
        text_y = setpoint + 0.03 * (y_ub - y_lb)
        if text_y > y_ub * 0.95: text_y = setpoint - 0.03 * (y_ub - y_lb)

        plt.text(0, text_y, 'nominal')

    if save_as:
        plt.savefig(path.join(PathPlots, save_as), dpi=kwargs.get('dpi'))

    plt.show()
    return


def plt_ExhaustSpeeds(results, CT_selection, load_levels_pu, amb_T_RH, pump_ctrl, save_as=None, **kwargs):
    """Plots the exhaust speeds of multiple CTs (intended for the largest CT per fan size)"""
    def_kwargs = {
        'xlabel': 'Load [%]',
        'ylabel': '[m/s]',
        'title': 'Exhaust Air Speed vs. Load',
        'legend_kw': {'loc': 'lower right', 'title': 'CT size and fan diameter'},
    }
    kwargs.update({key: val for key, val in def_kwargs.items() if key not in kwargs})
    kwargs.update({key: val for key, val in common_def_kwargs.items() if key not in kwargs})

    nCT = CT_selection.shape[0]
    CT_color_seq = ('#5499C7', '#52BE80', '#F39C12', '#E74C3C', '#8E44AD', '#839192', '#2E4053')
    Tamb, RHamb = amb_T_RH

    # ----------------------------------------------------- PLOT
    plt.figure(figsize=kwargs['figsize'])

    for CTidx in range(nCT):
        plt.plot(load_levels_pu * 100, results[Tamb, RHamb, pump_ctrl, 'exhaust speed'][:, CTidx].magnitude,
                 label='{} kW, {} m'.format(CT_selection['Capacity [kW]'].iat[CTidx],
                                            CT_selection['Fan diameter [m]'].iat[CTidx]),
                 color=CT_color_seq[CTidx], )

    ax = plt.gca()
    # ax = basic_plot_polishing(ax, **kwargs)
    plt.text(0.86, 0.42, 'Ambient Conditions', fontdict={'fontweight': 0}, horizontalalignment='center',
             transform=ax.transAxes)
    plt.text(0.86, 0.37, '{}°C, {} RH'.format(Tamb, RHamb), horizontalalignment='center', transform=ax.transAxes)

    if save_as:
        plt.savefig(path.join(PathPlots, save_as), dpi=kwargs.get('dpi'))

    plt.show()
    return


common_def_kwargs = {
    'figsize': (9.6, 6),
    'legend': True,
    'xlabel_kw': {'fontsize': 12.5, },
    'xticks_kw': {'fontsize': 11},
    'ylabel_kw': {'fontsize': 12.5, },
    'yticks_kw': {'fontsize': 11},
    'title_kw': {'fontsize': 13},
    'dpi': 300,
}
