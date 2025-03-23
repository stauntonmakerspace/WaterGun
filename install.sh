It took my 8 day but i found my solution there ; https://github.com/opencv/opencv-python/issues/530 For my opinion its work better in new python3.8 virtual environment

OPENCV_VER="master"
TMPDIR=$(mktemp -d)
cd "${TMPDIR}"
git clone --branch ${OPENCV_VER} --depth 1 --recurse-submodules --shallow-submodules https://github.com/opencv/opencv-python.git opencv-python-${OPENCV_VER}
cd opencv-python-${OPENCV_VER}
export ENABLE_CONTRIB=0
export ENABLE_HEADLESS=1
export CMAKE_ARGS="-D WITH_GSTREAMER=ON -D WITH_GTK=ON"
/home/makersign/Projects/WaterGun/.venv/bin/python -m pip wheel . --verbose
# Install OpenCV
/home/makersign/Projects/WaterGun/.venv/bin/python -m pip install opencv_python*.whl