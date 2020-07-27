__all__ = ['CBA', 'DERVETParams', 'MicrogridResult', 'MicrogridResult', 'run_DERVET', "MicrogridScenario", "storagevet", ]
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import os
import sys
# ADD DERVET and STORAGEVET TO PYTHONPATH BEFORE IMPORTING ANY LIBRARIES OTHERWISE IMPORTERROR
dervet_path = os.path.abspath(__file__)
# add dervet (source root) to PYTHONPATH
sys.path.insert(0, dervet_path)
# dervet's directory path is the first in sys.path

# determine storagevet path (absolute path)
storagevet_path = os.path.join(dervet_path, 'storagevet')
# add storagevet (source root) to PYTHONPATH
sys.path.insert(0, storagevet_path)

