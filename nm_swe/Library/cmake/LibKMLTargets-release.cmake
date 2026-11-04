#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "kmlbase" for configuration "Release"
set_property(TARGET kmlbase APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(kmlbase PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "C;CXX"
  IMPORTED_LINK_INTERFACE_LIBRARIES_RELEASE "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/expat.lib;C:/Users/mgersh/nm_swe/nm_swe/Library/lib/z.lib;C:/Users/mgersh/nm_swe/nm_swe/Library/lib/minizip.lib;C:/Users/mgersh/nm_swe/nm_swe/Library/lib/uriparser.lib;C:/Users/mgersh/nm_swe/nm_swe/Library/lib/expat.lib"
  IMPORTED_LOCATION_RELEASE "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlbase.lib"
  )

list(APPEND _cmake_import_check_targets kmlbase )
list(APPEND _cmake_import_check_files_for_kmlbase "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlbase.lib" )

# Import target "kmldom" for configuration "Release"
set_property(TARGET kmldom APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(kmldom PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LINK_INTERFACE_LIBRARIES_RELEASE "kmlbase"
  IMPORTED_LOCATION_RELEASE "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmldom.lib"
  )

list(APPEND _cmake_import_check_targets kmldom )
list(APPEND _cmake_import_check_files_for_kmldom "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmldom.lib" )

# Import target "kmlxsd" for configuration "Release"
set_property(TARGET kmlxsd APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(kmlxsd PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LINK_INTERFACE_LIBRARIES_RELEASE "kmlbase"
  IMPORTED_LOCATION_RELEASE "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlxsd.lib"
  )

list(APPEND _cmake_import_check_targets kmlxsd )
list(APPEND _cmake_import_check_files_for_kmlxsd "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlxsd.lib" )

# Import target "kmlengine" for configuration "Release"
set_property(TARGET kmlengine APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(kmlengine PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LINK_INTERFACE_LIBRARIES_RELEASE "kmlbase;kmldom"
  IMPORTED_LOCATION_RELEASE "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlengine.lib"
  )

list(APPEND _cmake_import_check_targets kmlengine )
list(APPEND _cmake_import_check_files_for_kmlengine "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlengine.lib" )

# Import target "kmlconvenience" for configuration "Release"
set_property(TARGET kmlconvenience APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(kmlconvenience PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LINK_INTERFACE_LIBRARIES_RELEASE "kmlengine;kmldom;kmlbase"
  IMPORTED_LOCATION_RELEASE "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlconvenience.lib"
  )

list(APPEND _cmake_import_check_targets kmlconvenience )
list(APPEND _cmake_import_check_files_for_kmlconvenience "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlconvenience.lib" )

# Import target "kmlregionator" for configuration "Release"
set_property(TARGET kmlregionator APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(kmlregionator PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LINK_INTERFACE_LIBRARIES_RELEASE "kmlbase;kmldom;kmlengine;kmlconvenience"
  IMPORTED_LOCATION_RELEASE "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlregionator.lib"
  )

list(APPEND _cmake_import_check_targets kmlregionator )
list(APPEND _cmake_import_check_files_for_kmlregionator "C:/Users/mgersh/nm_swe/nm_swe/Library/lib/kmlregionator.lib" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
