"""Fixed owner-approved grip offsets captured from the running 2.5 session.

Quaternion order is xyzw. Applied on the RIGHT of camera-to-controller
orientation, exactly as Space.session_grip was applied in 2.5. No auto-centering.
These are a grip convention, not a universal camera calibration or drift fix.
"""
DEFAULT_GRIP_XYZW = {
    1: (0.030236185580325748, 0.33490344927214416, 0.40456399430854934, 0.8504430770229625),
    2: (0.06604510179278716, 0.5383109640464054, 0.35669842913800975, -0.7606744252090288),
}
