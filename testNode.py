import cv2
import time
import datetime
from collections import defaultdict 
import numpy as np
import TelemetryServer
import yaml

def draw_enter_end_zones(cv_image,horizontal=False):
        if horizontal:
            cv_image = cv2.line(cv_image, (0, int(height*enter_zone_part)), (width, int(height*enter_zone_part)), (0,0,255), 1)
            cv_image = cv2.line(cv_image, (0, int(height*end_zone_part)), (width, int(height*end_zone_part)), (0,0,255), 1)
        else:
            cv_image = cv2.line(cv_image, (int(width*enter_zone_part),0), (int(width*enter_zone_part),height), (0,0,255), 1)
            cv_image = cv2.line(cv_image, (int(width*end_zone_part), 0), (int(width*end_zone_part), height), (0,0,255), 1)
        return cv_image

track_history = defaultdict(lambda: [[], False, 0])
count = 0

def is_track_pass_board(track, horizontal = False):
    is_left_point_exist = 0
    is_right_point_exist = 0
    left_point_frame = 0
    right_point_frame = 0

    if horizontal:
        index = 1
        criteria = height
    else:
        index = 0
        criteria = width

    for i in range(len(track)):
        point = track[i]
        if (point[index] < int(criteria * enter_zone_part)):
            is_left_point_exist = 1
            left_point_frame = i
        if (point[index] > int(criteria * end_zone_part)):
            is_right_point_exist = 1
            right_point_frame = i

    if (is_left_point_exist * is_right_point_exist == 1 and
            left_point_frame < right_point_frame):
        return True
    return False

def is_track_actual(track):
    if (len(track) < 2):
            return False
    return True

def update_tracks(results, horizontal = False):
    global count
    if(results[0].boxes.id != None):
        boxes = results[0].boxes.xywh.cpu()
        track_ids = results[0].boxes.id.int().cpu().tolist()
        if horizontal:
            index = 1
            criteria = height
        else:
            index = 0
            criteria = width
        for box, track_id in zip(boxes, track_ids):
            x, y, w, h = box
            track_C = track_history[track_id]
            track = track_C[0]
            is_counted = track_C[1]
            track.append((float(x),float(y)))
            if track[-1][index] > criteria * end_zone_part and is_counted == False:
                if is_track_pass_board(track, horizontal = horizontal):
                    count += 1
                    track_C[1] = True
    else:
        track_ids = []

    ## clear lost
    keys = list(track_history.keys())
    for key in keys:
        if not key in track_ids:
            if( track_history[key][2] < 30):
                track_history[key][2] += 1
            else:
                del track_history[key]
            
        
def draw_count(cv_image):
    return cv2.putText(cv_image, f"{count}", (30,30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 
                       2, cv2.LINE_AA)

def draw_tracks(cv_image): 
    for key,values in track_history.items(): 
        color = (0, 0, 255)
        position = values[0][-1]
        status = values[1]
        if (status):
            color = (0, 255, 0)
        cv_image = cv2.circle(cv_image, (int(position[0]), int(position[1])), 0, color, 3) 
    return cv_image
        
        

def runserver():
    flask_server.app.run(debug=False, host="0.0.0.0")

def saveImg(frame, FarmId, LineId, DateTime, folder = f"/home/pi/EggCounter/frames/{FarmId}/{LineId}/{datetime.today().strftime('%Y-%m-%d')}"):
    if not os.path.exists(folder): 
        os.makedirs(folder) 
    strTime = datetime.datetime.fromtimestamp(DateTime).strftime('%H_%M_%S')
    cv2.imwrite(folder + f"{stTime}.jpg", frame)


def insert_counted_toDB(): 
    global count
    global last_frame
    FarmId = config["device"]["FarmId"]
    LineId = config["device"]["LineId"]
    remoteTelemetry = TelemetryServer.TelemetryServer(host = config["server"]["hostname"],
                                      port = config["server"]["port"],
                                      FarmId = FarmId,
                                      LineId = LineId)
    last_count = 0
    while True:
        time.sleep(60) 
        needSaveFrame.clear()
        needSaveFrame.wait()
        datetime = time.time()
        flask_server.insert(datetime, count - last_count)
        remoteTelemetry.send_count(count - last_count, datetime)
        saveImg(last_frame, FarmId, LineId, datetime)
        last_count = count

def main_thread():
    global last_frame
    i = 0
    while True:
        start = time.time()
        annotated_frame = np.full((320,240,3), 150)
        if not needSaveFrame.is_set():
            last_frame = annotated_frame.copy()
            needSaveFrame.set()
        annotated_frame = draw_count(annotated_frame)
        print(f"fps = {(1/(time.time() - start)):.2f} EGGS = {count}",end='\r')

            # # Visualize the results on the frame
            # if flask_server.frames_queue.qsize() < 10:
            #     flask_server.frames_queue.put_nowait(annotated_frame.copy())
           


def load_yaml_with_defaults(file_path):
    with open(file_path, "r") as file:
        config = yaml.safe_load(file)
        return config

if __name__ == "__main__":
    config = load_yaml_with_defaults("config.yaml")
   
    needSaveFrame = threading.Event()
    saveImgLock = threading.Lock()
    #thrServer = threading.Thread(target = runserver)
   # thrServer.start()

    thrInsert = threading.Thread(target = insert_counted_toDB)
    thrInsert.start()

    main_thread()
    thrInsert.join()
    #thrServer.join()
