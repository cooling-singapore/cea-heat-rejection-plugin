"""
This tool creates heat rejection for a group of buildings, split into sensible and latent heat.
Based on a previously defined Cooling Tower Model (available in: https://github.com/cooling-singapore/CoolingTower)
"""
import cea.config
import cea.inputlocator
import cea.plugin
import numpy as np
import pandas as pd
import geopandas as gpd
import csv
import os
import warnings

from itertools import groupby
from cea.utilities import epwreader
from cea.utilities.dbf import dbf_to_dataframe
from cea.utilities.date import get_date_range_hours_from_year
from cea.demand import demand_writers
from cea import MissingInputDataException

from cea_heat_rejection_plugin.groups_helper import *
from cea_heat_rejection_plugin import BASE_CT_THRESHOLD
from cea_heat_rejection_plugin.utilities.DK_thermo import HumidAir
from cea_heat_rejection_plugin.utilities.coolingtowers import set_ambient, simulate_CT, parse_BldgToCTs, calc_CTheatload

CT_CATALOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'catalog.csv')

__author__ = "Cooling Singapore (Luis Santos, Reynold Mok)"
__copyright__ = "Copyright 2020, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Luis Santos, Reynold Mok, David Kayanan, Jimeno Fonseca"]
__license__ = "MIT"
__version__ = "1.0"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"


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
        cooling_demand = building_demand['DC_cs_kWh'].abs() + building_demand['E_cs_kWh'].abs() + building_demand['Qcs_kWh'].abs()  #Assuring heat rejection is positive
        building_demands[building_name] = cooling_demand

    building_demands['time'] = building_demands.index.values
    return building_demands


def get_building_properties(locator):
    zone_geometry_df = gpd.GeoDataFrame.from_file(locator.get_zone_geometry())
    building_properties = zone_geometry_df[['Name', 'height_ag', 'floors_ag']].set_index('Name')
    return building_properties


def group_files_exist(locator, config):

    # verify that the necessary group files exist
    def daysim_results_exist(building_name):
        return os.path.exists(locator.get_radiation_building(building_name))

    building_names = config.demand.buildings
    return all(daysim_results_exist(building_name) for building_name in building_names)


def get_building_groups(config,locator):

    # Specifying types of systems within CEA database
    building_supply = dbf_to_dataframe(locator.get_building_supply())

    # Check if the user included a building group in the inputs folder
    if not os.path.isfile(locator.get_groups()):
        raise MissingInputDataException("Missing building groups data in scenario. Consider running groups helper first.")

    # Separating building groups with and without cooling towers:
    building_groups = pd.read_csv(locator.get_groups())
    print("Building groups: \n",building_groups) #print table with all groups of buildings
    data_ct = {'Group':[],'Buildings':[]}
    data_no_ct = {'Group': [], 'Buildings': []}
    for i, grouping in building_groups.iterrows():
        supply_system =[]
        building_list = grouping.Buildings.split(",")
        for building in building_list:
            building_supply_system = building_supply.loc[building_supply.Name == building]
            supply_system.append(building_supply_system.type_cs.values)
        # Check if all buildings of the same group have the same supply system:
        if all(x == supply_system[0] for x in supply_system):
            # Check if the buildings from a group have cooling tower:
            if str(supply_system[0][0]) in config.heat_rejection.cooling_tower_systems:
                data_ct['Group'].append(grouping.Group)
                data_ct['Buildings'].append(grouping.Buildings)
            else:
                data_no_ct['Group'].append(grouping.Group)
                data_no_ct['Buildings'].append(grouping.Buildings)
        else:
            raise ValueError("Buildings from the same group must have the same supply system. Please check type_cs for"+str(building_list))
    building_groups_ct = pd.DataFrame(data_ct)
    building_groups_no_ct = pd.DataFrame(data_no_ct)
    print("Building groups with cooling tower (district cooling included): \n",building_groups_ct) #print table only with buildings that have cooling tower

    return building_groups,building_groups_ct, building_groups_no_ct


def main(config):
    """
    This tool creates outputs of hourly heat that is rejected by each building group. Heat rejection is defined as the
    total heat that leaves the building through air-conditioning, which includes the cooling load and the energy required by cooling systems.
    In case the group system is defined by a wet cooling tower, the model splits the heat rejected into sensible
    and latent fractions. For the remaining cases, heat is assumed to be 100% sensible heat.
    The calculations of the cooling tower were previously developed in https://github.com/cooling-singapore/CoolingTower

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
    if max(weather['relhum_percent']) > 100:
        warnings.warn("Original weather has relative humidity above 100%. A maximum of 100% will be considered.")
    rel_humidity = np.clip(weather['relhum_percent']/100, 0.0, 1.0) # Make sure values are between 0 and 1 (inclusive)

    air_i, WBT = set_ambient(drybulb_temp, rel_humidity)

    # read the thermal load
    building_demands = get_building_demands(locator)
    building_properties = get_building_properties(locator)
    building_groups, building_groups_ct, building_groups_no_ct = get_building_groups(config,locator)

    # compute extra properties
    max_load_series = pd.DataFrame({'Max_load_kWh': building_demands.max(0)})
    min_cap_opp = pd.DataFrame({'Min_Cap_opp': building_demands.replace(0, np.NaN).min(0) / building_demands.max(0)})
    building_demands = building_demands.replace(np.NaN, 0.0)
    building_properties = building_properties.merge(max_load_series, left_index=True, right_index=True)
    building_properties = building_properties.merge(min_cap_opp, left_index=True, right_index=True)
    building_properties.head()

    building_demands = pd.concat([building_demands], ignore_index=True)
    building_demands['time'] = building_demands.index.values

    # agreagate thermal loads
    group_demand_dict = {}

    for i, row in building_groups_ct.iterrows():
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

    if group_demand_df.empty:
        print('There are no buildings with cooling towers, therefore the Heat Rejection model will not be activated.')
    else:
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

        # Output results and save
        sensible_share_ct = pd.DataFrame()
        latent_share_ct = pd.DataFrame()

        # Get the split between sensible and latent heat
        for cooling_tower in res['air_o'].columns:
            sensible_share = list()
            latent_share = list()
            for i in range(0, len(air_i)):
                sensible_share.append((HumidAir.sensible_latent_heat_split(air_i[i], res['air_o'][cooling_tower][i]))[0])
                latent_share.append((HumidAir.sensible_latent_heat_split(air_i[i], res['air_o'][cooling_tower][i]))[1])
            sensible_share_ct[cooling_tower] = sensible_share
            latent_share_ct[cooling_tower] = latent_share

        sensible_share_group = pd.DataFrame(columns=group_demand_df.columns)
        latent_share_group = pd.DataFrame(columns=group_demand_df.columns)

        # Average the results for the 3 Cooling Towers for each group
        for i, group in enumerate(group_demand_df.columns):
            cooling_towers = [f"CT{i*3 + j}" for j in range(3)]
            sensible_share_group[group] = sensible_share_ct[cooling_towers].mean(axis=1)
            latent_share_group[group] = latent_share_ct[cooling_towers].mean(axis=1)

        # Save outputs
        year = weather['year'][0]
        for group in building_groups_ct.Group:
            Q_reject_kWh = group_demand_df
            if group in list(building_groups_ct.Group):
                Q_reject_sens_kWh = group_demand_df.mul(sensible_share_group)
                Q_reject_lat_kWh = group_demand_df.mul(latent_share_group)
            else:
                Q_reject_sens_kWh = group_demand_df
                Q_reject_lat_kWh = group_demand_df*0
            building = building_groups.loc[building_groups.Group == group].Buildings

            output = pd.DataFrame()
            output['Buildings'] = list(building)*len(Q_reject_kWh)
            output['Date'] = get_date_range_hours_from_year(year)
            output['Q_reject_kWh'] = Q_reject_kWh[group]
            output['Q_reject_sens_kWh'] = Q_reject_sens_kWh[group]
            output['Q_reject_lat_kWh'] = Q_reject_lat_kWh[group]

            get_heat_rejection_folder = locator._ensure_folder(locator.scenario, 'outputs', 'data', 'heat_rejection')
            # output.to_csv(os.path.join(get_heat_rejection_folder,group+'_'+str(np.array(building)[0])+'.csv')) #to save groups with building names (removed because can get too long)
            output.to_csv(os.path.join(get_heat_rejection_folder, group + '.csv'), index=False)
        print('Heat Rejection calculation is finished, check heat_rejection in data folder (outputs)')


if __name__ == '__main__':
    main(cea.config.Configuration())
