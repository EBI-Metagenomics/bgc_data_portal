# Copyright 2024 EMBL - European Bioinformatics Institute
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os

# Load Pfam to GO Slim mappings
pfam2goslim_file = os.path.join(os.path.dirname(__file__), "data/pfam2goSlim.json")
with open(pfam2goslim_file) as f:
    pfam2go_dict = json.load(f)

# Create dictionary of GO slim molecular function
pfamToGoSlim = {
    pfam: list(
        {
            desc.capitalize()
            for desc, go_type in go_slims
            if go_type == "molecular_function"
        }
    )
    for pfam, go_slims in pfam2go_dict.items()
}
pfamToGoSlim = {pfam: go_slims for pfam, go_slims in pfamToGoSlim.items() if go_slims}
