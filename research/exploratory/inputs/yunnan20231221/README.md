# Yunnan University, 21 December 2023: exposed source excerpts

Downloaded on 8 October 2026 from [Mendeley Part III, version 3](https://data.mendeley.com/datasets/nxk9r22wd6/3), by Xiaoyan Wang,
Jingjing Yang, Ming Huang and Zixiao Peng. The dataset is licensed **CC BY
4.0**. Interpretation and activity times come from the [original article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11220923/), DOI
10.1016/j.dib.2024.110302. These are public research recordings, not our
acquisition or independently certified observations.

| Original source | Bytes | SHA-256 |
|---|---:|---|
| [1221/Raw data/12.zip](https://data.mendeley.com/public-files/datasets/nxk9r22wd6/files/e9fb2c4a-76ec-40c8-be9c-cb889b3da8d5/file_downloaded) | 41,065,688 | `de19343259eafbdaa5ec309dbc2875366e3cecef829340400b05fa8eab89370d` |
| [1221/Raw data/18.zip](https://data.mendeley.com/public-files/datasets/nxk9r22wd6/files/9b2fb8bf-f947-4b9e-b397-5edd95b67240/file_downloaded) | 41,599,269 | `defef3aef7469e2ff49559da7b1985e3bfcd249881109dec46464cd527f656c2` |
| [Processed data/pvtSolution12.json](https://data.mendeley.com/public-files/datasets/nxk9r22wd6/files/b81683d3-a25c-469a-bcac-fa12ca39590e/file_downloaded) | 1,339,974 | `d26784ec04a4b2da30a8cdf5fa07389785327c417c330ecf5429f0df89dae029` |
| [Processed data/observation12.json](https://data.mendeley.com/public-files/datasets/nxk9r22wd6/files/4a7e35e0-abe6-4682-9201-842200f692dd/file_downloaded) | 108,706,850 | `16ac99b065d8dc93df2edb6809c9ab8052fa8aefd4ef47ee464e973b5572a674` |

`receiver_messages.tar.gz` retains **unchanged member bytes** of all RXM-RAWX,
NAV-PVT and NAV-CLOCK JSON files in the two ZIPs, under `12/` and `18/`, plus
the complete original processed PVT file under `processed/`. Other message
classes remain available in the original ZIPs; no new interpretation of them
is claimed. Packaging changes the container, not the JSON bytes. There are
21,448 retained files; the compressed container is 14,092,753 bytes. Its digest
is in the result, alongside that of the derived observation excerpt.

`processed_observation12_first_epoch.json` is a **derived first-epoch extract**:
`{key: values[0] for key, values in json.loads(original_bytes).items()}`,
serialized with `json.dump(..., indent=2, allow_nan=False)`. It is not the
original 108 MB source. It retains every field of that first processed epoch
to compare field identities with the original simultaneous RAWX message.
The complete processed observation file is unnecessary for that comparison.

The two original hours were chosen as the first available hour in the
published disturbance period and the first full hour after it. Qualification
and source values were opened before the detailed Table 13 windows were
transcribed. There is no observation-blind or prospective claim. Window
ends are represented as exclusive for descriptive counting; the fourth
attack continues beyond the retained first hour.

Direct HTTP downloads returned 403 in this environment. Ordinary browser
download controls worked. Use the dataset's folder navigation and download
links if a command-line client is rejected; no account or token was needed.
