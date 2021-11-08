"""
author: Halley Nathwani

This file works as a sandbox to run various DER-VET simulations in order to develop
the emissions reduction module.

Feel free to comment out sections. Each can be run independently (just be sure to read the comments).
"""
import pandas as pd
from dervet.DERVET import DERVET
import os
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# ERCOT_DIR = Path(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\ERCOT_2014_inputs")
# CAISO_DIR = Path(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\CAISO_2014_inputs")


# """ Run ERCOT case"""
# os.chdir(ERCOT_DIR)  # set directory to input file directory
# ERCOT_MP = ERCOT_DIR / "ercot2014andPV.csv"
# # ERCOT_MP = ERCOT_DIR / "ercot2014.csv"
# # run case
# case = DERVET(ERCOT_MP, verbose=True)
# case_results = case.solve()
# # grab pareto analysis results
# ercot_results = case_results.instances[0].get_results()  # get results of the first instance of the results
# drill_down_dfs = ercot_results.drill_down_dict  # get all drill down dfs
# pareto_curve_ercot = drill_down_dfs['emissions_pareto_curve']  # select only the emissions pareto curve dataframe

# """Run Caiso case"""
# os.chdir(CAISO_DIR)
# CAISO_MP = CAISO_DIR / "caiso2014_15min_pv.csv"
# # CAISO_MP = CAISO_DIR / "caiso2014_15min.csv"
# # run case
# case = DERVET(CAISO_MP, verbose=True)
# case_results = case.solve()
# # grab pareto analysis results
# case_results = case_results.instances[0]
# caiso_results = case_results.get_results()
# drill_down_dfs = case_results.drill_down_dict
# pareto_curve_caiso = drill_down_dfs['emissions_pareto_curve']

"""Plot Pareto Curves in same plot"""
# ercot_results_dir = Path(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\ercot_2014_ess_pv")
# pareto_curve_ercot = pd.read_csv(ercot_results_dir/"emissions_pareto_curve_ercot2014.csv", index_col=0)
# caiso_results_dir = Path(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\caiso_2014_ess_pv")
# pareto_curve_caiso = pd.read_csv(caiso_results_dir/"emissions_pareto_curve_caiso2014.csv", index_col=0)

# # ercot_results_dir = Path(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\ercot_2014_ess")
# # pareto_curve_ercot = pd.read_csv(ercot_results_dir/"emissions_pareto_curve_ercot2014.csv", index_col=0)
# # caiso_results_dir = Path(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\caiso_2014_ess_15min")
# # pareto_curve_caiso = pd.read_csv(caiso_results_dir/"emissions_pareto_curve_caiso2014_15min.csv", index_col=0)

# sns.set_theme()
# plt.style.use('seaborn-whitegrid')
# plt.rcParams["font.weight"] = "bold"

# fig1, ax = plt.subplots(1, 1, figsize=(12, 6))
# # delta_system_emissions = pareto_curve.sort_values()
# plt.axhline(linewidth=2, color='k')
# plt.axvline(linewidth=2, color='k')
# ax.plot(pareto_curve_ercot['Change in Indirect Emissions'].values, pareto_curve_ercot['DA ETS'].values, marker="o", color='darkviolet', linestyle='dashed', label='ERCT')
# ax.plot(pareto_curve_caiso['Change in Indirect Emissions'].values, pareto_curve_caiso['DA ETS'].values, marker="o", color='green', linestyle='dashed', label='CAMX')
# ax.set_ylabel('Profit', fontsize=15, fontweight='bold')
# ax.set_xlabel('Change in Indirect Emissions', fontsize=15, fontweight='bold')
# ax.grid(True)
# plt.subplots_adjust(left=0.1)
# for txt in pareto_curve_caiso.index:
#     ax.annotate(txt, (pareto_curve_ercot.loc[txt, 'Change in Indirect Emissions'] + .01, pareto_curve_ercot.loc[txt, 'DA ETS'] + .01))
#     ax.annotate(txt, (pareto_curve_caiso.loc[txt, 'Change in Indirect Emissions'] + .01, pareto_curve_caiso.loc[txt, 'DA ETS'] + .01))
# # ax.set_title('')
# plt.legend()
# plt.show()



"""Plot Pareto curves on different plots"""
ercot_results_dir = Path(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\ercot_2014_ess_pv")
pareto_curve_ercot = pd.read_csv(ercot_results_dir/"emissions_pareto_curve_ercot2014.csv", index_col=0)
caiso_results_dir = Path(r"C:\Users\phna001\Box\stuff\2021 TI Generalizing Emission Estimation in Microgrid Planning\Data\DER-VET simulations\caiso_2014_ess_pv")
pareto_curve_caiso = pd.read_csv(caiso_results_dir/"emissions_pareto_curve_caiso2014.csv", index_col=0)

sns.set_theme()
plt.style.use('seaborn-whitegrid')
plt.rcParams["font.weight"] = "bold"

monetary_conversion = 1000
mass_conversion = 1000
fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
ax1.plot(pareto_curve_ercot['Change in Indirect Emissions'].values/mass_conversion, pareto_curve_ercot['DA ETS'].values/monetary_conversion, marker="o", color='k', linestyle='dashed', label='ERCT')
ax1.set_ylabel('Profit (Thousand $)', fontsize=15, fontweight='bold')
ax1.set_xlabel('Emission Impact (tonnes)', fontsize=15, fontweight='bold')
ax1.grid(True)
ax2.plot(pareto_curve_caiso['Change in Indirect Emissions'].values/mass_conversion, pareto_curve_caiso['DA ETS'].values/monetary_conversion, marker="o", color='k', linestyle='dashed', label='CAMX')
# ax2.set_ylabel('Profit ($)', fontsize=15, fontweight='bold')
ax2.set_xlabel('Emission Impact (tonnes)', fontsize=15, fontweight='bold')
ax2.grid(True)
for txt in pareto_curve_caiso.index:
    if float(txt) >= 1:
        txt = str(int(txt))
    if float(txt) <= 0.2:
        v_buff = -1
        h_buff = 0
    if float(txt) > 0.2:
        v_buff = -0.5
        h_buff = 10

    ax1.annotate(txt, (pareto_curve_ercot.loc[float(txt), 'Change in Indirect Emissions']/mass_conversion + h_buff, pareto_curve_ercot.loc[float(txt), 'DA ETS']/monetary_conversion + v_buff))
    ax2.annotate(txt, (pareto_curve_caiso.loc[float(txt), 'Change in Indirect Emissions']/mass_conversion + h_buff, pareto_curve_caiso.loc[float(txt), 'DA ETS']/monetary_conversion + v_buff))
ax1.set_title('ERCOT', fontsize=15, fontweight='bold')
ax2.set_title('CAMX', fontsize=15, fontweight='bold')
plt.subplots_adjust(wspace=0.15)
plt.show()
