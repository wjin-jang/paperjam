# PaperJam OS External Buildroot Tree
# Include all package makefiles

include $(sort $(wildcard $(BR2_EXTERNAL_PAPERJAM_PATH)/package/*/*.mk))
