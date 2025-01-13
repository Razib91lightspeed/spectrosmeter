#!/usr/bin/env python3

import cv2
import time
import numpy as np
from specFunctions import wavelength_to_rgb, savitzky_golay, peakIndexes, readcal, writecal, background, generateGraticule
import base64
import argparse
from picamera2 import Picamera2
import libcamera

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--fullscreen", help="Fullscreen (Native 800*480)", action="store_true")
group.add_argument("--waterfall", help="Enable Waterfall (Windowed only)", action="store_true")
args = parser.parse_args()
dispFullscreen = False
dispWaterfall = False
if args.fullscreen:
    print("Fullscreen Spectrometer enabled")
    dispFullscreen = True
if args.waterfall:
    print("Waterfall display enabled")
    dispWaterfall = True

frameWidth = 800
frameHeight = 600

picam2 = Picamera2()
picamGain = 10.0

video_config = picam2.create_video_configuration(
    main={"format": 'RGB888', "size": (frameWidth, frameHeight)},
    controls={"FrameDurationLimits": (33333, 33333)}
)
picam2.configure(video_config)
picam2.start()

title1 = 'PySpectrometer 2 - Spectrograph'
title2 = 'PySpectrometer 2 - Waterfall'
stackHeight = 320 + 80 + 80

if dispWaterfall:
    cv2.namedWindow(title2, cv2.WINDOW_GUI_NORMAL)
    cv2.resizeWindow(title2, frameWidth, stackHeight)
    cv2.moveWindow(title2, 200, 200)

if dispFullscreen:
    cv2.namedWindow(title1, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(title1, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
else:
    cv2.namedWindow(title1, cv2.WINDOW_GUI_NORMAL)
    cv2.resizeWindow(title1, frameWidth, stackHeight)
    cv2.moveWindow(title1, 0, 0)

savpoly = 7
mindist = 50
thresh = 20

calibrate = False
clickArray = []
cursorX = 0
cursorY = 0

def handle_mouse(event, x, y, flags, param):
    global clickArray, cursorX, cursorY
    mouseYOffset = 160
    if event == cv2.EVENT_MOUSEMOVE:
        cursorX = x
        cursorY = y
    if event == cv2.EVENT_LBUTTONDOWN:
        mouseX = x
        mouseY = y - mouseYOffset
        clickArray.append([mouseX, mouseY])

cv2.setMouseCallback(title1, handle_mouse)

font = cv2.FONT_HERSHEY_SIMPLEX
intensity = [0] * frameWidth
holdpeaks = False
measure = False
recPixels = False

msg1 = ""
saveMsg = "No data saved"

waterfall = np.zeros([320, frameWidth, 3], dtype=np.uint8)
waterfall.fill(0)

frameWidth = 800
caldata = readcal(frameWidth)
wavelengthData = caldata[0]
calmsg1 = caldata[1]
calmsg2 = caldata[2]
calmsg3 = caldata[3]

graticuleData = generateGraticule(wavelengthData)
tens = graticuleData[0]
fifties = graticuleData[1]

def snapshot(savedata):
    now = time.strftime("%Y%m%d--%H%M%S")
    timenow = time.strftime("%H:%M:%S")
    imdata1 = savedata[0]
    graphdata = savedata[1]
    if dispWaterfall:
        imdata2 = savedata[2]
        cv2.imwrite("waterfall-" + now + ".png", imdata2)
    cv2.imwrite("spectrum-" + now + ".png", imdata1)
    f = open("Spectrum-" + now + '.csv', 'w')
    f.write('Wavelength,Intensity\r\n')
    for x in zip(graphdata[0], graphdata[1]):
        f.write(str(x[0]) + ',' + str(x[1]) + '\r\n')
    f.close()
    message = "Last Save: " + timenow
    return message

while True:
    frame = picam2.capture_array()
    y = int((frameHeight / 2) - 40)
    x = 0
    h = 80
    w = frameWidth
    cropped = frame[y:y + h, x:x + w]
    bwimage = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    rows, cols = bwimage.shape
    halfway = int(rows / 2)
    cv2.line(cropped, (0, halfway - 2), (frameWidth, halfway - 2), (255, 255, 255), 1)
    cv2.line(cropped, (0, halfway + 2), (frameWidth, halfway + 2), (255, 255, 255), 1)

    decoded_data = base64.b64decode(background)
    np_data = np.frombuffer(decoded_data, np.uint8)
    img = cv2.imdecode(np_data, 3)
    messages = img

    graph = np.zeros([320, frameWidth, 3], dtype=np.uint8)
    graph.fill(255)

    textoffset = 12
low = int(round(min(wavelengthData)))
high = int(round(max(wavelengthData)))
step = max(1, len(wavelengthData) // max(1, (high - low)))  # Ensure step is at least 1

# Debugging output
print(f"wavelengthData: {wavelengthData}")
print(f"low: {low}, high: {high}, step: {step}")

for i in range(0, len(wavelengthData), step):
    if int(wavelengthData[i]) % 10 == 0 and int(wavelengthData[i]) % 50 != 0:
        cv2.line(graph, (i, 15), (i, 320), (200, 200, 200), 1)

    for i in range(0, len(wavelengthData), step // 2):
        if int(wavelengthData[i]) % 10 == 0 and int(wavelengthData[i]) % 50 != 0:
            cv2.line(graph, (i, 15), (i, 320), (200, 200, 200), 1)

    for i in range(frameWidth):
        if i < cols:
            dataminus1 = bwimage[halfway - 1, i]
            datazero = bwimage[halfway, i]
            dataplus1 = bwimage[halfway + 1, i]
            data = (int(dataminus1) + int(datazero) + int(dataplus1)) / 3
            intensity[i] = int(data)
        else:
            intensity[i] = 0

        if holdpeaks:
            if data > intensity[i]:
                intensity[i] = data
        else:
            intensity[i] = data

    if dispWaterfall:
        wdata = np.zeros([1, frameWidth, 3], dtype=np.uint8)
        index = 0
        for i in intensity:
            rgb = wavelength_to_rgb(round(wavelengthData[index]))
            luminosity = intensity[index] / 255
            b = int(round(rgb[0] * luminosity))
            g = int(round(rgb[1] * luminosity))
            r = int(round(rgb[2] * luminosity))
            wdata[0, index] = (r, g, b)
            index += 1
        contrast = 2.5
        brightness = 10
        wdata = cv2.addWeighted(wdata, contrast, wdata, 0, brightness)
        waterfall = np.insert(waterfall, 0, wdata, axis=0)
        waterfall = waterfall[:-1].copy()

        hsv = cv2.cvtColor(waterfall, cv2.COLOR_BGR2HSV)

    if not holdpeaks:
        intensity = savitzky_golay(intensity, 17, savpoly)
        intensity = np.array(intensity)
        intensity = intensity.astype(int)
        holdmsg = "Holdpeaks OFF"
    else:
        holdmsg = "Holdpeaks ON"

    index = 0
    for i in intensity:
        rgb = wavelength_to_rgb(round(wavelengthData[index]))
        r = rgb[0]
        g = rgb[1]
        b = rgb[2]
        cv2.line(graph, (index, 320), (index, 320 - i), (b, g, r), 1)
        cv2.line(graph, (index, 319 - i), (index, 320 - i), (0, 0, 0), 1, cv2.LINE_AA)
        index += 1

    textoffset = 12
    thresh = int(thresh)
    indexes = peakIndexes(intensity, thres=thresh / max(intensity), min_dist=mindist)
    for i in indexes:
        height = intensity[i]
        height = 310 - height
        wavelength = round(wavelengthData[i], 1)
        cv2.rectangle(graph, ((i - textoffset) - 2, height), ((i - textoffset) + 60, height - 15), (0, 255, 255), -1)
        cv2.rectangle(graph, ((i - textoffset) - 2, height), ((i - textoffset) + 60, height - 15), (0, 0, 0), 1)
        cv2.putText(graph, str(wavelength) + 'nm', (i - textoffset, height - 3), font, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.line(graph, (i, height), (i, height + 10), (0, 0, 0), 1)

    if measure:
        cv2.line(graph, (cursorX, cursorY - 140), (cursorX, cursorY - 180), (0, 0, 0), 1)
        cv2.line(graph, (cursorX - 20, cursorY - 160), (cursorX + 20, cursorY - 160), (0, 0, 0), 1)
        cv2.putText(graph, str(round(wavelengthData[cursorX], 2)) + 'nm', (cursorX + 5, cursorY - 165), font, 0.4, (0, 0, 0), 1, cv2.LINE_AA)

    if recPixels:
        cv2.line(graph, (cursorX, cursorY - 140), (cursorX, cursorY - 180), (0, 0, 0), 1)
        cv2.line(graph, (cursorX - 20, cursorY - 160), (cursorX + 20, cursorY - 160), (0, 0, 0), 1)
        cv2.putText(graph, str(cursorX) + 'px', (cursorX + 5, cursorY - 165), font, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
    else:
        clickArray = []

    if clickArray:
        for data in clickArray:
            mouseX = data[0]
            mouseY = data[1]
            cv2.circle(graph, (mouseX, mouseY), 5, (0, 0, 0), -1)
            cv2.putText(graph, str(mouseX), (mouseX + 5, mouseY), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0))

    spectrum_vertical = np.vstack((messages, cropped, graph))
    cv2.line(spectrum_vertical, (0, 80), (frameWidth, 80), (255, 255, 255), 1)
    cv2.line(spectrum_vertical, (0, 160), (frameWidth, 160), (255, 255, 255), 1)
    cv2.putText(spectrum_vertical, calmsg1, (490, 15), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(spectrum_vertical, calmsg3, (490, 33), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(spectrum_vertical, saveMsg, (490, 51), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(spectrum_vertical, "Gain: " + str(picamGain), (490, 69), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(spectrum_vertical, holdmsg, (640, 15), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(spectrum_vertical, "Savgol Filter: " + str(savpoly), (640, 33), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(spectrum_vertical, "Label Peak Width: " + str(mindist), (640, 51), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(spectrum_vertical, "Label Threshold: " + str(thresh), (640, 69), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.imshow(title1, spectrum_vertical)

    if dispWaterfall:
        waterfall_vertical = np.vstack((messages, cropped, waterfall))
        cv2.line(waterfall_vertical, (0, 80), (frameWidth, 80), (255, 255, 255), 1)
        cv2.line(waterfall_vertical, (0, 160), (frameWidth, 160), (255, 255, 255), 1)
        textoffset = 12

        for positiondata in fifties:
            for i in range(162, 480):
                if i % 20 == 0:
                    cv2.line(waterfall_vertical, (positiondata[0], i), (positiondata[0], i + 1), (0, 0, 0), 2)
                    cv2.line(waterfall_vertical, (positiondata[0], i), (positiondata[0], i + 1), (255, 255, 255), 1)
            cv2.putText(waterfall_vertical, str(positiondata[1]) + 'nm', (positiondata[0] - textoffset, 475), font, 0.4, (0, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(waterfall_vertical, str(positiondata[1]) + 'nm', (positiondata[0] - textoffset, 475), font, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.putText(waterfall_vertical, calmsg1, (490, 15), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(waterfall_vertical, calmsg3, (490, 33), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(waterfall_vertical, saveMsg, (490, 51), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(waterfall_vertical, "Gain: " + str(picamGain), (490, 69), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(waterfall_vertical, holdmsg, (640, 15), font, 0.4, (0, 255, 255), 1, cv2.LINE_AA)

        cv2.imshow(title2, waterfall_vertical)

    keyPress = cv2.waitKey(1)
    if keyPress == ord('q'):
        break
    elif keyPress == ord('h'):
        holdpeaks = not holdpeaks
    elif keyPress == ord("s"):
        graphdata = []
        graphdata.append(wavelengthData)
        graphdata.append(intensity)
        if dispWaterfall:
            savedata = [spectrum_vertical, graphdata, waterfall_vertical]
        else:
            savedata = [spectrum_vertical, graphdata]
        saveMsg = snapshot(savedata)
    elif keyPress == ord("c"):
        calcomplete = writecal(clickArray)
        if calcomplete:
            caldata = readcal(frameWidth)
            wavelengthData = caldata[0]
            calmsg1 = caldata[1]
            calmsg2 = caldata[2]
            calmsg3 = caldata[3]
            graticuleData = generateGraticule(wavelengthData)
            tens = graticuleData[0]
            fifties = graticuleData[1]
    elif keyPress == ord("x"):
        clickArray = []
    elif keyPress == ord("m"):
        recPixels = False
        measure = not measure
    elif keyPress == ord("p"):
        measure = False
        recPixels = not recPixels
    elif keyPress == ord("o"):
        savpoly = min(savpoly + 1, 15)
    elif keyPress == ord("l"):
        savpoly = max(savpoly - 1, 0)
    elif keyPress == ord("i"):
        mindist = min(mindist + 1, 100)
    elif keyPress == ord("k"):
        mindist = max(mindist - 1, 0)
    elif keyPress == ord("u"):
        thresh = min(thresh + 1, 100)
    elif keyPress == ord("j"):
        thresh = max(thresh - 1, 0)
    elif keyPress == ord("t"):
        picamGain = min(picamGain + 1, 50.0)
        picam2.set_controls({"AnalogueGain": picamGain})
        print("Camera Gain: " + str(picamGain))
    elif keyPress == ord("g"):
        picamGain = max(picamGain - 1, 0.0)
        picam2.set_controls({"AnalogueGain": picamGain})
        print("Camera Gain: " + str(picamGain))

cv2.destroyAllWindows()