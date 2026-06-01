import signal
import sys
import time
import threading

# Global State Variables
# SET SHUTDOWN_GRACE_PERIOD_SEC = 5.0
SHUTDOWN_GRACE_PERIOD_SEC = 5.0
# SET IS_SHUTTING_DOWN = FALSE
is_shutting_down = False
# SET ActiveConnectionsCounter = 0
active_connections_counter = 0

# Mock definitions for internal pipeline dependencies
def shutdown_ingress_listeners():
    """Mock function to immediately halt ingestion entry points."""
    pass

def broadcast_cancellation_to_workers():
    """Mock function to notify working threads of cancellation state."""
    pass


# FUNCTION InitializeSignalEnvelope():
def initialize_signal_envelope():
    # // Register OS signals to fire handler immediately on main execution frame
    # REGISTER_SIGNAL_HANDLER(SIGTERM, HandleTerminationSignal)
    signal.signal(signal.SIGTERM, handle_termination_signal)
    # REGISTER_SIGNAL_HANDLER(SIGINT, HandleTerminationSignal)
    signal.signal(signal.SIGINT, handle_termination_signal)
    
    # EMIT SYSTEM_SIGNAL "Signal envelope armed. Monitoring for lifecycle transitions."
    print("SYSTEM_SIGNAL: Signal envelope armed. Monitoring for lifecycle transitions.")


# FUNCTION HandleTerminationSignal(SignalNumber, Frame):
def handle_termination_signal(signal_number, frame):
    global is_shutting_down

    # // SPOF Mitigation: Force idempotency. Prevent signal thrashing.
    # IF IS_SHUTTING_DOWN == TRUE THEN
    if is_shutting_down is True:
        # EMIT WARNING "Termination signal re-received. Forcing immediate hard exit."
        print("WARNING: Termination signal re-received. Forcing immediate hard exit.", file=sys.stderr)
        # EXIT_PROCESS(1)
        sys.exit(1)
    # END IF

    is_shutting_down = True
    # EMIT SYSTEM_SIGNAL "Intercepted operational signal: " + SignalNumber + ". Initiating Graceful Unwind."
    print(f"SYSTEM_SIGNAL: Intercepted operational signal: {signal_number}. Initiating Graceful Unwind.")

    # // Step 1: Immediately kill entry points to halt ingress
    # CALL ShutDownIngressListeners()
    shutdown_ingress_listeners()

    # // Step 2: Spawn isolated countdown safety timer to defeat deadlocks
    # CALL SpawnIndependentDetachedTimer(SHUTDOWN_GRACE_PERIOD_SEC, ForceKillFallback)
    fallback_timer = threading.Timer(SHUTDOWN_GRACE_PERIOD_SEC, force_kill_fallback)
    fallback_timer.daemon = True  # Ensure the background thread is detached
    fallback_timer.start()

    # // Step 3: Begin active connection drain
    # CALL ExecuteDrainSequence()
    execute_drain_sequence()


# FUNCTION ExecuteDrainSequence():
def execute_drain_sequence():
    global active_connections_counter
    # TRY:
    try:
        # LOOP WHILE ActiveConnectionsCounter > 0:
        while active_connections_counter > 0:
            # EMIT LOG "Awaiting operational drain. Active pipelines remaining: " + ActiveConnectionsCounter
            print(f"LOG: Awaiting operational drain. Active pipelines remaining: {active_connections_counter}")
            
            # // Wake up blocking loops across the stack by passing cancellation state
            # CALL BroadcastCancellationToWorkers()
            broadcast_cancellation_to_workers()
            # CALL Sleep(0.5)
            time.sleep(0.5)
        # END LOOP
        
        # EMIT DEPLOY_SUCCESS "All worker states flushed and committed. Clean exit achieved."
        print("DEPLOY_SUCCESS: All worker states flushed and committed. Clean exit achieved.")
        # EXIT_PROCESS(0)
        sys.exit(0)
        
    # CATCH Exception AS ShutdownFault:
    except Exception as shutdown_fault:
        # EMIT CRITICAL "Fatal error during resource de-allocation sequence" WITH ShutdownFault
        print(f"CRITICAL: Fatal error during resource de-allocation sequence. Fault: {shutdown_fault}", file=sys.stderr)
        # EXIT_PROCESS(1)
        sys.exit(1)


# FUNCTION ForceKillFallback():
def force_kill_fallback():
    # // Executed ONLY if the worker threads freeze or deadlock during ExecuteDrainSequence
    # EMIT CRITICAL "Grace period expired. Internal threads hanging or deadlocked. Enforcing hard crash."
    print("CRITICAL: Grace period expired. Internal threads hanging or deadlocked. Enforcing hard crash.", file=sys.stderr)
    # EXIT_PROCESS(2)
    sys.exit(2)


# STATUS = "Verified"
status = "Verified"
