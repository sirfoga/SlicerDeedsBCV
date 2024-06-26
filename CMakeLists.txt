cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(SlicerDeedsBCV)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/sirfoga/SlicerDeedsBCV.git")
set(EXTENSION_CATEGORY "Registration")
set(EXTENSION_CONTRIBUTORS "Stefano Fogarollo (IGS, Innsbruck University)")
set(EXTENSION_DESCRIPTION "This extension makes available deedsBCV in Slicer.")
#set(EXTENSION_ICONURL "https://raw.githubusercontent.com/lassoan/SlicerElastix/master/SlicerElastix.png")
#set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/lassoan/SlicerElastix/master/Screenshot01.jpg")
set(EXTENSION_DEPENDS "NA") # Specified as a space separated string, a list or 'NA' if any
set(EXTENSION_BUILD_SUBDIRECTORY inner-build)

set(SUPERBUILD_TOPLEVEL_PROJECT inner)

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})
mark_as_superbuild(Slicer_DIR)

find_package(Git REQUIRED)
mark_as_superbuild(GIT_EXECUTABLE)

#-----------------------------------------------------------------------------
# SuperBuild setup
option(${EXTENSION_NAME}_SUPERBUILD "Build ${EXTENSION_NAME} and the projects it depends on." ON)
mark_as_advanced(${EXTENSION_NAME}_SUPERBUILD)
if(${EXTENSION_NAME}_SUPERBUILD)
  include("${CMAKE_CURRENT_SOURCE_DIR}/SuperBuild.cmake")
  return()
endif()

#-----------------------------------------------------------------------------
# Extension modules
## NEXT_MODULE

#-----------------------------------------------------------------------------
set(EXTENSION_CPACK_INSTALL_CMAKE_PROJECTS)
#list(APPEND EXTENSION_CPACK_INSTALL_CMAKE_PROJECTS "${Foo_DIR};Foo;RuntimeLibraries;/")
set(${EXTENSION_NAME}_CPACK_INSTALL_CMAKE_PROJECTS "${EXTENSION_CPACK_INSTALL_CMAKE_PROJECTS}" CACHE STRING "List of external projects to install" FORCE)

#-----------------------------------------------------------------------------
list(APPEND CPACK_INSTALL_CMAKE_PROJECTS "${CMAKE_BINARY_DIR};${EXTENSION_NAME};ALL;/")
list(APPEND CPACK_INSTALL_CMAKE_PROJECTS "${${EXTENSION_NAME}_CPACK_INSTALL_CMAKE_PROJECTS}")
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
