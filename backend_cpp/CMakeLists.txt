cmake_minimum_required(VERSION 3.10)
project(cpp_backend)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Add pthread for httplib
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread")

include_directories(${CMAKE_SOURCE_DIR})

add_executable(cpp_backend main.cpp)

# Link pthread library
target_link_libraries(cpp_backend pthread)
