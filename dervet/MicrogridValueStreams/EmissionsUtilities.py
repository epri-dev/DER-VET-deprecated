"""
author: Halley Nathwani

There are 2 sections to this file. First it reads in raw MEF data and wrangles it into timeseries data
for DER-VET to use during it's run. The second contains code that plots figures of results in a Box folder.

Feel free to comment out sections, but not the function. Each section below the defined functions
can be run independently (just be sure to read the comments).
"""
import pandas as pd
from storagevet.Library import create_timeseries_index
import matplotlib.pyplot as plt
import matplotlib.dates as dates
import numpy as np
CAlC_METHOD = "Regression"
raw_mef = pd.read_csv(fr"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\Marginal Emission Factor Data\{CAlC_METHOD}\Generation-MARREG-EMIT-egrid-bySeasonalTOD2014.csv", index_col=0)
DATA_YEAR = 2014
REGION = 'ERCT'  # 'CAMX'  # 'ERCT'
POLLUTANT = 'co2'

print(raw_mef.region.unique())  # ['CAISO' 'ERCOT' 'ISONE' 'MISO' 'NYISO' 'PJM' 'SPP']
# print(raw_mef.pollutant.unique())  # ['so2', 'nox', 'pm25', 'co2']

# PLOTTING CONSTANTS
SUBPLOT_WSPACE = .05


def convert_monthly_tod_mef_to_hourly(simulation_year: list, res):
    # select all datapoints relating to selected region and pollutant
    region = raw_mef[(raw_mef.region == REGION) & (raw_mef.pollutant == POLLUTANT)]

    # create df with a hourly datetime index of year of data
    hourly_df = pd.DataFrame(columns=['MEF'], index=create_timeseries_index(simulation_year, f'{int(res*60)}min'))

    # fill df with emission factors (g/MWh)
    monthly_groupby = region.groupby('month')
    for month, month_data in monthly_groupby:
        for hour in month_data.hour.unique():
            # print(f'month-hour: {month}-{hour}')
            hourly_df.loc[(hourly_df.index.hour == hour) & (hourly_df.index.month == month), 'MEF'] = month_data[month_data.hour == hour].factor.values
    hourly_df = hourly_df.astype('float64')
    hourly_df = hourly_df
    # save hourly df
    hourly_df.to_csv(rf"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\Marginal Emission Factor Data\{CAlC_METHOD}\processed\{simulation_year}_hourly_{REGION}_{POLLUTANT}.csv")
    return hourly_df.loc[:, 'MEF']


def convert_seasonal_hod_mef_to_hourly(simulation_year: list, res):
    season_to_months = {
        'Summer': [5, 6, 7, 8, 9],
        'Trans': [4, 10],
        'Winter': [11, 12, 1, 2, 3],

    }
    # select all datapoints relating to selected region and pollutant
    region = raw_mef[(raw_mef.region == REGION) & (raw_mef.pollutant == POLLUTANT)]

    # create df with a hourly datetime index of year of data
    hourly_df = pd.DataFrame(columns=['MEF'], index=create_timeseries_index(simulation_year, f'{int(res*60)}min'))

    # fill df with emission factors (kg/MWh)
    season_groupby = region.groupby('season')
    for season, season_data in season_groupby:
        for hour in season_data.hour.unique():
            # print(f'month-hour: {month}-{hour}')
            hourly_df.loc[(hourly_df.index.hour == hour) & (hourly_df.index.month.isin(season_to_months[season])), 'MEF'] = season_data[season_data.hour == hour].factor.values
    hourly_df = hourly_df.astype('float64')
    hourly_df = hourly_df/1000
    # save hourly df
    hourly_df.to_csv(rf"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\Marginal Emission Factor Data\{CAlC_METHOD}\processed\{'_'.join([str(yr) for yr in simulation_year])}_shod_{REGION}_{POLLUTANT}.csv")
    return hourly_df.loc[:, 'MEF']


def convert_caiso_energy_price(simulation_years: list, res):
    temp = pd.read_csv(
        r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\Price Data\20140101-20150101 CAISO Average Price.csv",
        index_col=0)
    temp.index = pd.DatetimeIndex(temp.index)
    temp_ind = create_timeseries_index(simulation_years, f'{int(res*60)}min')
    caiso_price = temp[temp.index.isin(temp_ind)]
    caiso_price = caiso_price.resample('5min').mean()
    caiso_price = caiso_price.fillna(0)
    caiso_price.index.name = "Datetime (he)"
    caiso_price.columns = ['DA Price ($/kWh)']
    caiso_price['DA Price ($/kWh)'] = caiso_price['DA Price ($/kWh)'] / 1000
    caiso_price.to_csv(
        r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\CAISO_2014_validation_inputs\timeseries.csv")
    caiso_price.to_csv(
        r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\Price Data\processed_caiso_avg.csv")
    return caiso_price

foo = convert_seasonal_hod_mef_to_hourly([2014], 0.25)
# site_load = pd.read_csv(r"C:\Users\phna001\Box\Public Hourly Load Data\TMY\USA_TX_San.Antonio-Kelly.AFB.722535_TMY3\RefBldgHospitalNew2004_v1.3_7.1_2A_USA_TX_HOUSTON.csv", index_col=0)
# # site_load = pd.read_csv(r"C:\Users\phna001\Box\Public Hourly Load Data\TMY\USA_CA_Oakland.Intl.AP.724930_TMY3\RefBldgHospitalNew2004_7.1_5.0_3C_USA_CA_SAN_FRANCISCO.csv", index_col=0)
# # plt.style.use('seaborn-whitegrid')
# fig, ax = plt.subplots(figsize=(12.7, 4.6))
# load= site_load.loc[:,'Electricity:Facility [kW](Hourly)']
# load.plot()
# # ax.fill_between(load.index, 0, load, facecolor="0.5", alpha=0.5, step="pre")
# ax.set_ylabel("Power [kW]")
# ax.set_title('San Antonio TX TMY Commercial Hospital Load')
# ax.set_axisbelow(True)
# plt.show()


# time_series_results = pd.read_csv(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\ercot\timeseries_results_ercot.csv", index_col=0)

# pareto_curve = pd.read_csv(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\ercot\emissions_pareto_curve_ercot.csv", index_col=0)
#
# pareto_curve = pareto_curve.loc[: ,["Avoided Demand Charge","Avoided Energy Charge","System Emissions"]]
# pareto_curve['Total Avoided Charges'] = pareto_curve.loc[: ,"Avoided Demand Charge"] + pareto_curve.loc[: ,"Avoided Energy Charge"]
#
# fig, axes = plt.subplots(2, 1, figsize=(12.7, 4.6))
# plt.style.use('seaborn-whitegrid')
# plt.xscale('log')
# axes[0].scatter(pareto_curve.index, pareto_curve['Total Avoided Charges'])
# axes[0].set_xscale('log')
# axes[0].set_ylim((-40000,20000))
# axes[0].set_xlim((1e-10,1))
# axes[0].grid(True)
# axes[1].scatter(pareto_curve.index, pareto_curve['System Emissions'])
# axes[1].set_xscale('log')
# axes[1].set_ylim((5.7e12,5.85e12))
# axes[1].set_xlim((1e-10,1))
# plt.grid(True)

# load= site_load.loc[:,'Electricity:Facility [kW](Hourly)']
# load.plot()
# # ax.fill_between(load.index, 0, load, facecolor="0.5", alpha=0.5, step="pre")
# ax.set_ylabel("Power [kW]")
# ax.set_title('San Antonio TX TMY Commercial Hospital Load')
# ax.set_axisbelow(True)
# plt.show()

# 'HB_BUSAVG', 'HB_HOUSTON', 'HB_HUBAVG', 'HB_NORTH', 'HB_SOUTH',
# 'HB_WEST', 'LZ_AEN', 'LZ_CPS', 'LZ_HOUSTON', 'LZ_LCRA', 'LZ_NORTH',
# 'LZ_RAYBN', 'LZ_SOUTH', 'LZ_WEST'
# df = pd.concat(pd.read_excel(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\RTM EROCT\rpt.00013061.0000000000000000.RTMLZHBSPP_2014.xlsx", sheet_name=None), ignore_index=True)
# datetime_df = pd.DatetimeIndex(df['Delivery Date'])
# df.loc[:, 'Year'] = datetime_df.year
# df.loc[:, 'Hour'] = df['Delivery Hour']-1
# df.loc[:, 'Day'] = datetime_df.day
# df.loc[:, 'Month'] = datetime_df.month
# df.loc[:, 'Minute'] = (df['Delivery Interval']-1)*15
# df.loc[:, 'Datetime (hb)'] = pd.to_datetime(df[['Year', 'Month', 'Day', 'Hour', 'Minute']])
#
# rt_prices_df = pd.pivot_table(df, index='Datetime (hb)', columns=['Settlement Point Name', 'Settlement Point Type'],
#                               values='Settlement Point Price', aggfunc=np.mean)
# # temp_df = df[(df['Settlement Point Name']=='LZ_CPS') & (df['Settlement Point Type']=='LZ')]
# temp_df = df[(df['Settlement Point Name']=='HB_BUSAVG')]
# rt_energy_price = pd.DataFrame(data={'DA ETS ($/MWh)': temp_df['Settlement Point Price'].values}, index=temp_df['Datetime (hb)'])
# rt_energy_price.plot()

""" Load Data and Plot regression-based MEFs in CAMX and ERCT"""
# POLLUTANT = 'co2'
# raw_mef2 = pd.read_csv(rf"C:\Users\phna001\Box\Marginal Emission Factor Data\Regression\processed\2014_shod_CAMX_{POLLUTANT}.csv", index_col=0)
# raw_mef = pd.read_csv(rf"C:\Users\phna001\Box\Marginal Emission Factor Data\Regression\processed\2014_shod_ERCT_{POLLUTANT}.csv", index_col=0)
# raw_mef2.index = pd.DatetimeIndex(raw_mef2.index)
# raw_mef2 = raw_mef2.resample("1h").mean()
# raw_mef2 = raw_mef2/1000
# raw_mef.index = pd.DatetimeIndex(raw_mef.index)
# raw_mef = raw_mef.resample("1h").mean()
# num_plots = 3
# fig, axs = plt.subplots(1, num_plots, figsize=(14, 4.6), sharey=True)
# plt.style.use('seaborn-whitegrid')
# plt.rcParams["font.weight"] = "bold"
# axis_labels = ['March', 'October', 'June']
# for i, day_month in enumerate([(3,3), (10,10), (6,6)]):
#     ax = axs[i]
#     data_camx = raw_mef2.loc[(day_month[1] == raw_mef2.index.month) & (day_month[0] == raw_mef2.index.day), :]
#     data_erct = raw_mef.loc[(day_month[1] == raw_mef.index.month) & (day_month[0] == raw_mef.index.day), :]
#
#     ax.plot(data_camx, c = (0,.45,.7), ls = "-", lw = 2, label="CAMX", drawstyle="steps-post")
#     ax.plot(data_erct, c=(.8,.4,0), ls = "-", lw = 2, label="ERCT", drawstyle="steps-post")
#     if i == 0:
#         ax.set_ylabel("MEF [kg/MWh]", fontsize=15, fontweight='bold')
#     ax.set_xlabel(axis_labels[i], fontsize=15, fontweight='bold')
#     ax.xaxis.set_major_formatter(dates.DateFormatter('%H:%M'))
#     ax.set_axisbelow(True)
#     ax.grid(c="0.7", ls=":", lw=0.8)
#     ax.tick_params(axis='both', labelsize=12)
#     for label in ax.get_xticklabels() + ax.get_yticklabels():
#         label.set_fontweight('bold')
#     ax.set_xlim((data_erct.index[0], data_erct.index[-1]))
#     ax.grid(True)
# plt.legend(loc='upper center', bbox_to_anchor=(-.55, 1.16), ncol=2, fontsize=17)
# plt.tight_layout()
# plt.subplots_adjust(wspace=SUBPLOT_WSPACE)

""" Save regression-based v. dispatch-based MEFs in WECC as hourly timeseries CSVs and a dataframe"""
# REGION = 'WECC'
# DATA_YEAR = 2017
# POLLUTANT_LST = ['so2', 'nox', 'co2']
# df = pd.DataFrame()
# for POLLUTANT in POLLUTANT_LST:
#     CAlC_METHOD = 'Regression'
#     regression_mef = pd.read_csv(r"C:\Users\phna001\Box\Marginal Emission Factor Data\Regression\Generation-MARREG-EMIT-nerc-bySeasonalTOD2017.csv", index_col=0)
#     regression_mef = convert_seasonal_hod_mef_to_hourly([DATA_YEAR], 1, regression_mef)
#     df[f"{POLLUTANT.upper()}-{CAlC_METHOD}"] = regression_mef
#     CAlC_METHOD = 'Simulated'
#     dispatch_mef = pd.read_csv(r"C:\Users\phna001\Box\Marginal Emission Factor Data\Simulated\Generation-MARSIM-EMIT-nerc-bySeasonalTOD2017.csv", index_col=0)
#     dispatch_mef = convert_seasonal_hod_mef_to_hourly([DATA_YEAR], 1, dispatch_mef)
#     df[f"{POLLUTANT.upper()}-Dispatch"] = dispatch_mef
# df['CO2-Regression'] = df['CO2-Regression']/1000
# df['CO2-Dispatch'] = df['CO2-Dispatch']/1000

""" Load data and Plot regression-based v. dispatch-based MEFs in WECC"""
# POLLUTANT_LST = ['so2', 'nox', 'co2']
# df = pd.read_csv(r"C:\Users\phna001\Box\Marginal Emission Factor Data\processed\2017_hourly_shod_WECC.csv", index_col=0)
# df.index = pd.DatetimeIndex(df.index)
# num_plots_row = len([POLLUTANT_LST])
# num_plots_col = 3
# axis_labels = ['March', 'October', 'June']
# colors = [(0,.45,.7), (.8,.4,0), (.8,.6,.7)]
#
# fig, axs = plt.subplots(num_plots_row, num_plots_col, figsize=(19.5, 5), sharey=True)
# plt.style.use('seaborn-whitegrid')
# plt.rcParams["font.weight"] = "bold"
# for i, day_month in enumerate([(3,3), (10,10), (6,6)]):
#     ax = axs[i]
#     for j, pollutant in enumerate(POLLUTANT_LST):
#         data_simulated = df.loc[(day_month[1] == df.index.month) & (day_month[0] == df.index.day), f"{pollutant.upper()}-Dispatch"]
#         data_regression = df.loc[(day_month[1] == df.index.month) & (day_month[0] == df.index.day), f"{pollutant.upper()}-Regression"]
#         ax.axhline(y=0, color='grey', alpha=0.5)
#         ax.plot(data_simulated, c = colors[j] +(.5,), ls = "-", lw = 4, label=f"GHG MEF: {pollutant.upper()}\nMethod: Dispatch", drawstyle="steps-post")
#         ax.plot(data_regression, c=colors[j], ls = "--", lw = 2, label=f"GHG MEF: {pollutant.upper()}\nMethod: Regression", drawstyle="steps-post")
#         if i == 0:
#             ax.set_ylabel("MEF [kg/MWh]", fontsize=16, fontweight='bold')
#         ax.set_xlabel(axis_labels[i], fontsize=16, fontweight='bold')
#         ax.xaxis.set_major_formatter(dates.DateFormatter('%H:%M'))
#         ax.set_axisbelow(True)
#         ax.grid(c="0.7", ls=":", lw=0.8)
#         ax.tick_params(axis='both', labelsize=13)
#         for label in ax.get_xticklabels() + ax.get_yticklabels():
#             label.set_fontweight('bold')
#         ax.set_xlim((data_simulated.index[0], data_simulated.index[-1]))
#         ax.grid(True)
#
# plt.legend(loc='upper center', bbox_to_anchor=(-0.61, 1.16), ncol=6, fontsize=14)
# plt.tight_layout()
# plt.subplots_adjust(wspace=SUBPLOT_WSPACE)

""" Load and plot MEF vs. Energy Prices"""
# caiso_result2014 = pd.read_csv(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\caiso_2014_validation\timeseries_results_caiso2014.csv", index_col=0)
# caiso_result2014.index = pd.DatetimeIndex(caiso_result2014.index)  # (2,23) (2,1)
# ercot_result2014 = pd.read_csv(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\ercot_2014_validation\timeseries_results_ercot2014.csv", index_col=0)
# ercot_result2014.index = pd.DatetimeIndex(ercot_result2014.index)  # (4,5)
#
# colors = [(0,.45,.7), (.8,.4,0), (.8,.6,.7)]
#
#
# plt.style.use('seaborn-whitegrid')
# plt.rcParams["font.weight"] = "bold"
# for i, name, region, day_month in [(0, "ERCOT", ercot_result2014, (2,1)), (1, 'CAISO', caiso_result2014, (4,4))]:
#
#     fig, ax = plt.subplots(1,1, figsize=(8, 5))
#     data = region.loc[(day_month[0] == region.index.month) & ((day_month[1] < region.index.day) & (day_month[1]+7 > region.index.day)), :]
#     ax.axhline(y=0, color='grey', alpha=0.5)
#     ax.plot(data['MEF'], c = colors[0], ls = "-", lw = 2, label=f"MEF (kg/MWh)", drawstyle="steps-post")
#     ax.plot(data['Energy Price ($/kWh)'], c=colors[1], ls = "-", lw = 2, label=f"Energy Price($/kWh)", drawstyle="steps-post")
#     ax.set_ylabel(name, fontsize=16, fontweight='bold')
#     # if i == 0:
#     #     plt.legend(loc='upper center', bbox_to_anchor=(.5, 1), ncol=2, fontsize=14)
#     # ax.set_xlabel(name, fontsize=16, fontweight='bold')
#     ax.xaxis.set_major_formatter(dates.DateFormatter('%H:%M'))
#     ax.set_axisbelow(True)
#     ax.grid(c="0.7", ls=":", lw=0.8)
#     ax.tick_params(axis='both', labelsize=13)
#     for label in ax.get_xticklabels() + ax.get_yticklabels():
#         label.set_fontweight('bold')
#     ax.set_xlim((data.index[0], data.index[-1]))
#     ax.grid(True)
#     plt.legend(loc='lower center', bbox_to_anchor=(.5, 1), ncol=2, fontsize=16)
#     plt.tight_layout()
