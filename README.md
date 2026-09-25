# MorphoGenerator Tool (v1.0)

**MorphoGenerator Tool** is an advanced scientific desktop application for the parametric analysis, morphological design, CFD streamline visualization, and 3D exploration of **MorphoGenerator** microfluidic swirling devices.

---

## Key Features

### 1. 3D Model Explorer (Morphogenerator)
- Interactive **3D GLB Viewer** for inspecting internal geometry and flow channels.
- Real-time **clipping planes** (X, Y, Z axes) with adjustable offset, rotation, and lighting.
- Quick preset views (Top, Isometric, Front, Side).

### 2. Morphogenerator Parameters
- **Forward Design Mode**:
  - Real-time calculation of internal, external, and total **DSI** (Degree of Swirling Interaction) and petal geometry metrics.
  - Supports flow ratios Q in [0.01, 0.99] across nozzle counts N in {2, 3, 4, 5, 6}.
  - Dynamic side inlet configuration: select number of peripheral inlets (0 to 10), angular width (theta), angular rotation (0 to 360 deg), and spacing distribution.
  - **Synchronized Dual-Plane Visualization**:
    - **Top View Morphogenerator**: Inlet plane boundaries, blades (solid blue for down blades, dotted orange for upper blades), and peripheral inlet holes.
    - **Nozzle Plane**: Outlet plane streamline distribution, core fluid trace, and nozzle diameter boundary (R = 1.0 mm).
    - Responsive canvas auto-scaling with interactive draggable panel splitter.
- **Inverse Design & Parametric Sweep**:
  - Specify target DSI or perimeter metrics to analytically solve for matching (Q, N) pairs.
  - Instant side-by-side preview of predicted streamline topologies.

### 3. Correlation Plots
- High-resolution comparative plots of morphological polynomials.
- Interactive series selection, customizable styling, and direct image/vector export.

### 4. Settings & Accessibility
- **UI Scaling**: Custom number list scaling from 1.0x up to 3.0x (step 0.5x).
- **Internationalization (i18n)**: English and Italian language support.
- **Vibrant Navigation**: Full-color emoji iconography for clean, modern aesthetics.

### 5. Interactive User Guide
- Embedded documentation covering governing physical principles, DSI definitions, and operational tutorials.

---

## Installation & Setup

### Prerequisites
- Python **3.10+** (tested on Python 3.11 / 3.12)
- Windows 10 / 11

### 1. Clone or Download
`ash
cd Morpho_tool
`

### 2. Install Dependencies
`ash
pip install -r requirements.txt
`

### 3. Launch Application
`ash
python main.py
`

---

## Building the Standalone Executable (.exe)

To generate a standalone, single-file Windows executable with embedded assets and custom icon:

1. Run the build script:
   `cmd
   build.bat
   `
2. The compiled application will be generated in:
   `
   dist\\MorphoGenerator_Tool.exe
   `

---

## Project Architecture

`
Morpho_tool/
|-- app/
|   |-- core/                  # Analytical solvers & data models
|   |   |-- correlations.py    # Polynomial correlation coefficients
|   |   |-- solver.py          # Forward/Inverse/Sweep engines
|   |   |-- statistics.py      # Statistical evaluation metrics
|   |   +-- image_loader.py    # Streamline simulation image loader
|   |-- views/                 # UI View modules (CustomTkinter)
|   |   |-- glb_viewer.py      # 3D GLB model interactive viewer
|   |   |-- parameters.py      # Forward & Inverse parameter solver view
|   |   |-- plot_correlation.py# Polynomial correlation plotter
|   |   |-- settings.py        # Application settings & scaling
|   |   +-- guide.py           # In-app manual and documentation
|   |-- app.py                 # Main window, sidebar navigation & layout
|   |-- theme.py               # Color palettes, typography & dynamic icons
|   +-- i18n.py                # Multi-language localization dictionary
|-- morpho_visualizer.py       # Matplotlib streamline & dual-plane rendering engine
|-- streamline_extractor.py    # CFD streamline data synchronization & caching
|-- main.py                    # Application launch entry point
|-- build.bat                  # PyInstaller one-click build script
|-- app.ico                    # Multi-resolution application icon
+-- requirements.txt           # Python package dependencies
`

---

## License & Attribution
Developed for the **MorphoGenerator Project** - Universita degli Studi di Napoli Federico II.
