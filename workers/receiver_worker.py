# workers/receiver_worker.py
"""
Process-isolated Receiver Worker.
Handles SDR hardware interaction in a dedicated process to prevent buffer overflows
caused by Python's GIL or GC pauses during analysis.
"""

import time
import multiprocessing as mp
import numpy as np
import logging
import traceback
from pathlib import Path
from queue import Empty, Full

from receivers.sdr_manager import create_receiver
from receivers.base_receiver import ReceiverConfig

logger = logging.getLogger(__name__)

# Control commands
CMD_STOP = "STOP"
CMD_CONFIG = "CONFIG"

def sdr_process_loop(receiver_config: dict,
                     data_queue: mp.Queue,
                     command_queue: mp.Queue,
                     status_queue: mp.Queue):
    """
    The independent process function for SDR acquisition.
    """
    # Setup Logging in new process
    logging.basicConfig(level=logging.INFO)
    proc_logger = logging.getLogger("SDR-Process")
    
    receiver = None
    
    try:
        # Initialize Receiver
        # We reconstruct the config object from the dictionary
        # NOTE: ReceiverConfig dataclass usage might vary, ensuring we pass correct args
        config_obj = ReceiverConfig(**receiver_config)
        
        # Instantiate specific receiver class based on config (Factory pattern needed here)
        # We use the factory we created in receivers.sdr_manager
        
        receiver = create_receiver(config_obj)
        
        if not receiver.initialize_sdr():
            status_queue.put({"status": "ERROR", "message": "SDR Init Failed"})
            return
    
        receiver.start()
        status_queue.put({"status": "RUNNING"})
        
        # Define callback to push data to queue
        def push_samples(samples: np.ndarray, metrics):
            try:
                # We send metadata + small subsample for FFT, 
                # OR we send shared memory reference for huge data.
                # For < 10Msps, passing numpy arrays via Queue is acceptable but has overhead.
                # Optimization: Send only necessary chunks or use SharedMemory.
                
                if not data_queue.full():
                    # Copy data to ensure it's picklable and detached
                    data_queue.put_nowait((samples.copy(), metrics))
            except Full:
                proc_logger.warning("Data queue full - dropping samples")
            except Exception as e:
                proc_logger.error(f"Queue error: {e}")
    
        receiver.set_on_samples_callback(push_samples)
        
        # Main Loop
        while True:
            # Check for commands without blocking
            try:
                cmd = command_queue.get_nowait()
                if cmd == CMD_STOP:
                    break
            except Empty:
                pass
            
            # Keep process alive
            time.sleep(0.1)
            
    except Exception as e:
        status_queue.put({"status": "ERROR", "message": str(e)})
        proc_logger.error(f"Critical SDR Process Error: {traceback.format_exc()}")
    finally:
        if receiver:
            receiver.stop()
        status_queue.put({"status": "STOPPED"})

class ReceiverWorker:
    """
    Main interface to control the SDR process from the main application.
    """
    
    def __init__(self, config: ReceiverConfig):
        self.config = config
        self.process = None
        self.data_queue = mp.Queue(maxsize=100) # Buffer about 1-2 seconds of FFT frames
        self.command_queue = mp.Queue()
        self.status_queue = mp.Queue()
        
    def start(self):
        if self.process is not None and self.process.is_alive():
            logger.warning("Receiver process already running")
            return
    
        logger.info(f"Starting Receiver Process for {self.config.device}...")
        
        # Convert config to dict for serialization
        cfg_dict = self.config.__dict__
        
        self.process = mp.Process(
            target=sdr_process_loop,
            args=(cfg_dict, self.data_queue, self.command_queue, self.status_queue),
            daemon=True
        )
        self.process.start()
        
        # Wait for startup status
        try:
            status = self.status_queue.get(timeout=5.0)
            if status.get("status") == "ERROR":
                logger.error(f"Receiver failed to start: {status.get('message')}")
                self.process.terminate()
            else:
                logger.info("Receiver Process Started Successfully")
        except Empty:
            logger.error("Receiver process timed out during startup")
            
    def stop(self):
        if self.process and self.process.is_alive():
            self.command_queue.put(CMD_STOP)
            self.process.join(timeout=2.0)
            if self.process.is_alive():
                self.process.terminate()
            logger.info("Receiver Process Stopped")
            
    def get_data(self):
        """Generator to yield data from the queue"""
        while True:
            try:
                yield self.data_queue.get_nowait()
            except Empty:
                break
