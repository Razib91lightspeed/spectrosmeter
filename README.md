# 🔬 Raspberry Pi Camera Spectrometer (PySpectrometer 2)

## 🚀 What the Program Does

1. Captures video from PiCamera  
2. Extracts a thin horizontal slice containing the spectrum  
3. Converts pixel position → wavelength (nm) using calibration  
4. Calculates intensity per wavelength  
5. Detects spectral peaks  
6. Displays spectrum graph and optional waterfall  
7. Allows calibration  
8. Can save spectrum as PNG + CSV  

---

## 🧠 How It Works (Core Logic)

### 1️⃣ Capture Frame

    frame = picam2.capture_array()

Captures an RGB frame (e.g., 800×600).

---

### 2️⃣ Crop the Spectrum Line

    cropped = frame[y:y+h, x:x+w]
    bwimage = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

Only an ~80-pixel-high horizontal slice is used because the spectrum spreads horizontally.

---

### 3️⃣ Extract Intensity per Pixel

    data = (pixel_row1 + pixel_row2 + pixel_row3) / 3

This produces intensity values for each column (X-axis).

Result:

    intensity[x]

---

### 4️⃣ Convert Pixel → Wavelength

Using calibration polynomial:

    wavelength = C1*x^2 + C2*x + C3

Computed inside:

    readcal()

Result:

    wavelengthData[x]

Each pixel now maps to nanometers.

---

### 5️⃣ Smooth Signal

Uses Savitzky–Golay filter:

    savitzky_golay(intensity, 17, savpoly)

Reduces noise while preserving peaks.

---

### 6️⃣ Peak Detection

Using:

    peakIndexes()

Finds local maxima above threshold and labels them like:

    532 nm
    589 nm
    656 nm

---

### 7️⃣ Display Graph

Draws:
- Colored spectrum line (based on wavelength)
- Graticule lines every 10nm / 50nm
- Peak labels
- Intensity curve

---

### 8️⃣ Optional Waterfall Mode

    waterfall = np.insert(waterfall, 0, wdata)

Creates a real-time spectrogram over time.

Useful for:
- Plasma analysis
- Flame spectroscopy
- Laser monitoring

---

## 🎛 Keyboard Controls

| Key | Action |
|------|--------|
| q | Quit |
| s | Save spectrum |
| h | Hold peaks |
| c | Calibrate |
| m | Measure wavelength |
| p | Record pixel |
| o/l | Change smoothing |
| i/k | Change peak width |
| u/j | Change threshold |
| t/g | Change camera gain |

---

## ⚠ Important Technical Issue

Two `readcal()` functions are defined.  
The second one overwrites the first.

Also:

    wavelengthData = np.linspace(400, 1700, num=frameWidth)

Then later:

    wavelengthData = np.append(wavelengthData, wavelength)

This incorrectly doubles the array size and may cause:
- Wrong wavelength mapping
- Memory growth
- Graph misalignment

---

## 🔬 Signal Processing Pipeline

    Camera → Crop → Grayscale → Intensity Extraction
    → Calibration (Pixel → nm)
    → Smoothing
    → Peak Detection
    → Visualization
    → Optional Save

---

## 🧪 Applications

- Flame spectroscopy  
- Emission spectra analysis  
- Laser wavelength measurement  
- LED spectrum analysis  
- Material identification  
- Educational lab experiments  
