import cea.config
import cea.inputlocator
import cea.plugin
import numpy as np
import pandas as pd
import geopandas as gpd

from cea.utilities import epwreader

from cea_heat_rejection_plugin import BASE_CT_THRESHOLD
from cea_heat_rejection_plugin.utilities.DK_thermo import HumidAir
from cea_heat_rejection_plugin.utilities.coolingtowers import set_ambient, simulate_CT, parse_BldgToCTs, calc_CTheatload

CT_CATALOG_FILE = './data/catalog.csv'


class HeatRejectionPlugin(cea.plugin.CeaPlugin):
    """
    Define the plugin class - unless you want to customize the behavior, you only really need to declare the class. The
    rest of the information will be picked up from ``default.config``, ``schemas.yml`` and ``scripts.yml`` by default.
    """
    pass


def get_building_demands(locator):
    building_demands = pd.DataFrame()

    for building_name in locator.get_zone_building_names():
        building_demand = pd.read_csv(locator.get_demand_results_file(building_name))
        cooling_demand = building_demand['DC_cs_kWh'] + building_demand['E_cs_kWh'] + building_demand['Qcs_kWh']
        building_demands[building_name] = cooling_demand

    building_demands['time'] = building_demands.index.values
    return building_demands


def get_building_properties(locator):
    zone_geometry_df = gpd.GeoDataFrame.from_file(locator.get_zone_geometry())
    building_properties = zone_geometry_df[['Name', 'height_ag', 'floors_ag']].set_index('Name')
    return building_properties


def get_building_groups(locator):

    return None


def main(config):
    """
    This is the main entry point to your script. Any parameters used by your script must be present in the ``config``
    parameter. The CLI will call this ``main`` function passing in a ``config`` object after adjusting the configuration
    to reflect parameters passed on the command line / user interface

    :param cea.config.Configuration config: The configuration for this script, restricted to the scripts parameters.
    :return: None
    """

    locator = cea.inputlocator.InputLocator(config.scenario, config.plugins)

    # Read CT catalog
    CT_catalog = pd.read_csv(CT_CATALOG_FILE).set_index('CT')

    # Read scenario weather
    weather = epwreader.epw_reader(locator.get_weather_file())
    drybulb_temp = weather['drybulb_C']
    rel_humidity = np.clip(weather['relhum_percent']/100, 0.0, 1.0) # Make sure values are between 0 and 1 (inclusive)

    air_i, WBT = set_ambient(drybulb_temp, rel_humidity)

    # read the thermal load
    building_demands = get_building_demands(locator)
    building_properties = get_building_properties(locator)
    building_groups = get_building_groups(locator)

    # compute extra properties
    max_load_series = pd.DataFrame({'Max_load_kWh': building_demands.max(0)})
    min_cap_opp = pd.DataFrame({'Min_Cap_opp': building_demands.replace(0, np.NaN).min(0) / building_demands.max(0)})
    building_demands = building_demands.replace(np.NaN, 0.0)
    building_properties = building_properties.merge(max_load_series, left_index=True, right_index=True)
    building_properties = building_properties.merge(min_cap_opp, left_index=True, right_index=True)
    building_properties.head()

    building_demands = pd.concat([building_demands] * 365, ignore_index=True)
    building_demands['time'] = building_demands.index.values

    # agreagate thermal loads
    group_demand_dict = {}
    for i, row in building_groups.iterrows():
        building_list = row['Buildings'].split(",")
        demand = np.zeros(building_demands.shape[0])
        for building in building_list:
            demand += building_demands[building].values
        group_demand_dict[row['Group']] = demand
    group_demand_df = pd.DataFrame(group_demand_dict)

    # Size cooling towers per group
    def find_upper_neighbours(value, df, colname):
        exactmatch = df[df[colname] == value]
        if not exactmatch.empty:
            return exactmatch.index
        else:
            lowerneighbour_ind = df[df[colname] < value][colname].idxmax()
            upperneighbour_ind = df[df[colname] > value][colname].idxmin()
            upperneighbour = df[colname][upperneighbour_ind]
            return upperneighbour

    BldgToCTs = {}
    for (group, demand) in group_demand_df.iteritems():
        peak = max(demand)
        average = np.mean(demand.replace(0, np.NaN))
        baseload = BASE_CT_THRESHOLD * peak
        peak_unit_size = peak - average
        intermediate_unit_size = average - baseload
        base_unit_size = baseload

        # checks
        if peak_unit_size > CT_catalog['Capacity [kW]'].min():
            peak_unit_size = find_upper_neighbours(peak_unit_size, CT_catalog, 'Capacity [kW]')
        else:
            peak_unit_size = CT_catalog['Capacity [kW]'].min()

        if intermediate_unit_size > CT_catalog['Capacity [kW]'].min():
            intermediate_unit_size = find_upper_neighbours(intermediate_unit_size, CT_catalog, 'Capacity [kW]')
        else:
            intermediate_unit_size = CT_catalog['Capacity [kW]'].min()

        if base_unit_size > CT_catalog['Capacity [kW]'].min():
            base_unit_size = find_upper_neighbours(base_unit_size, CT_catalog, 'Capacity [kW]')
        else:
            base_unit_size = CT_catalog['Capacity [kW]'].min()

        BldgToCTs[group] = peak_unit_size, intermediate_unit_size, base_unit_size

    # split the load per Cooling tower capacity
    CT_load, results_columns = calc_CTheatload(group_demand_df, BldgToCTs, CT_catalog, t_from=None, t_to=None)


    CT_design = parse_BldgToCTs(BldgToCTs, CT_catalog)
    CT_design['groups'] = results_columns
    CT_design['ID'] = ['CT' + str(x) for x in CT_design.index]

    # simulate
    res = simulate_CT(CT_load, CT_design, air_i, pump_ctrl='Range limit', fan_ctrl=True)
    airflow = res['air flow']
    waterflow = res['water flow']
    HWT = res['HWT']
    waterflow = res['return water flow']
    T_drybulb_out = res['air_o']
    T_drybulb_out.columns = CT_design['ID']

    # Output results
    out = pd.DataFrame()
    for cooling_tower in res['air_o'].columns:
        _list = list()
        for i in range(0, len(air_i)):
            _list.append(HumidAir.sensible_latent_heat_split(air_i[i], res['air_o'][cooling_tower][i]))
        out[cooling_tower] = _list

    print(out)

if __name__ == '__main__':
    main(cea.config.Configuration())
