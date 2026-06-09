import { useState, useRef, useEffect, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  Alert,
  ScrollView,
  TextInput,
  Modal,
  FlatList,
  AppState,
} from "react-native";
import { useRouter } from "expo-router";
import { CameraView, useCameraPermissions } from "expo-camera";
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
import * as Notifications from "expo-notifications";
import { useJobStore } from "@/stores/jobStore";
import {
  createJob,
  getUploadUrl,
  confirmUpload,
  fetchCustomers,
  createCustomer,
  registerPushToken,
} from "@/api/client";
import { enqueueUpload, processQueue, initQueue, updateQueueJobId } from "@/utils/offlineQueue";
import { isOnline as checkIsOnline, subscribeToConnectivity } from "@/utils/network";
import { Customer } from "@/types";

const RETRY_INTERVAL_MS = 30000;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_REGEX = /^\+?[\d\s\-()]{7,15}$/;

export default function StartJobScreen() {
  const [camera, setCamera] = useState<CameraView | null>(null);
  const router = useRouter();
  const { setActiveJob, addMedia, reset: resetJobStore } = useJobStore();
  const [cameraPermission, requestPermission] = useCameraPermissions();
  const [showCamera, setShowCamera] = useState(false);
  const [capturedPhotos, setCapturedPhotos] = useState<string[]>([]);
  const [pendingPhotos, setPendingPhotos] = useState<string[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingUri, setRecordingUri] = useState<string | null>(null);
  const [pendingRecording, setPendingRecording] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [showCustomerPicker, setShowCustomerPicker] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [showCreateCustomer, setShowCreateCustomer] = useState(false);
  const [newCustomerName, setNewCustomerName] = useState("");
  const [newCustomerEmail, setNewCustomerEmail] = useState("");
  const [newCustomerPhone, setNewCustomerPhone] = useState("");
  const [newCustomerAddress, setNewCustomerAddress] = useState("");
  const recordingRef = useRef<Audio.Recording | null>(null);
  const [sound, setSound] = useState<Audio.Sound | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [description, setDescription] = useState("");
  const [isOnline, setIsOnline] = useState(true);
  const [isStartingJob, setIsStartingJob] = useState(false);
  const [isLoadingCustomers, setIsLoadingCustomers] = useState(false);

  useEffect(() => {
    const unsubscribe = subscribeToConnectivity(setIsOnline);
    return unsubscribe;
  }, []);

  const setupNotifications = async () => {
    try {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      if (existingStatus !== "granted") {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }
      if (finalStatus === "granted") {
        const tokenData = await Notifications.getExpoPushTokenAsync();
        await registerPushToken(tokenData.data);
      }
    } catch (err) {
      console.error("Failed to setup notifications:", err);
    }
  };

  const loadCustomers = async () => {
    if (!checkIsOnline()) return;
    setIsLoadingCustomers(true);
    try {
      const data = await fetchCustomers();
      setCustomers(data.customers || []);
    } catch (err) {
      console.error("Failed to load customers:", err);
    } finally {
      setIsLoadingCustomers(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initialization pattern
    loadCustomers();
    initQueue();
    setupNotifications();

    const retryInterval = setInterval(() => {
      if (checkIsOnline()) {
        processQueue().catch((err) => {
          console.error("processQueue failed in interval:", err);
        });
      }
    }, RETRY_INTERVAL_MS);

    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState === "active" && checkIsOnline()) {
        processQueue().catch((err) => {
          console.error("processQueue failed on app state change:", err);
        });
      }
    });

    return () => {
      clearInterval(retryInterval);
      subscription.remove();
    };
  }, []);

  const [isCreatingCustomer, setIsCreatingCustomer] = useState(false);

  const handleCreateCustomer = useCallback(async () => {
    if (!newCustomerName.trim() || newCustomerName.trim().length < 2) {
      Alert.alert("Required", "Customer name must be at least 2 characters");
      return;
    }
    if (newCustomerEmail.trim() && !EMAIL_REGEX.test(newCustomerEmail.trim())) {
      Alert.alert("Invalid Email", "Please enter a valid email address");
      return;
    }
    if (newCustomerPhone.trim() && !PHONE_REGEX.test(newCustomerPhone.trim())) {
      Alert.alert("Invalid Phone", "Please enter a valid phone number");
      return;
    }
    if (isCreatingCustomer) return;
    setIsCreatingCustomer(true);
    try {
      const customer = await createCustomer({
        name: newCustomerName.trim(),
        email: newCustomerEmail.trim() || undefined,
        phone: newCustomerPhone.trim() || undefined,
        address: newCustomerAddress.trim() || undefined,
      });
      setCustomers((prev) => [...prev, customer]);
      setSelectedCustomer(customer);
      setShowCreateCustomer(false);
      setNewCustomerName("");
      setNewCustomerEmail("");
      setNewCustomerPhone("");
      setNewCustomerAddress("");
    } catch (err) {
      console.error("Failed to create customer:", err);
      Alert.alert("Error", "Failed to create customer");
    } finally {
      setIsCreatingCustomer(false);
    }
  }, [newCustomerName, newCustomerEmail, newCustomerPhone, newCustomerAddress, isCreatingCustomer]);

  const uploadMediaForJob = useCallback(async (jobId: string) => {
    const allPending: string[] = [...pendingPhotos];
    if (pendingRecording) allPending.push(pendingRecording);

    const uploadTasks = allPending.map(async (uri) => {
      const contentType = uri.endsWith(".m4a") ? "audio/m4a" : "image/jpeg";
      const fileName = uri.endsWith(".m4a") ? `voice-${Date.now()}.m4a` : `photo-${Date.now()}.jpg`;
      try {
        const info = await FileSystem.getInfoAsync(uri);
        if (!info.exists) return;
        const upload = await getUploadUrl({
          job_id: jobId,
          file_name: fileName,
          content_type: contentType,
          file_size: info.size || 0,
        });
        await FileSystem.uploadAsync(upload.upload_url, uri, {
          fieldName: "file",
          httpMethod: "PUT",
          uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
        });
        await confirmUpload(upload.media_id);
        addMedia(upload.media_id);
      } catch (err) {
        console.error("Upload failed, enqueueing:", err);
        await enqueueUpload(jobId, uri, contentType);
      }
    });

    await Promise.all(uploadTasks);
    setPendingPhotos([]);
    setPendingRecording(null);
  }, [pendingPhotos, pendingRecording, addMedia]);

  const handleStartJob = useCallback(async () => {
    if (isStartingJob) return;
    if (!selectedCustomer) {
      Alert.alert("Required", "Please select a customer first");
      return;
    }
    if (!checkIsOnline()) {
      Alert.alert("Offline", "You need an internet connection to start a job. Please try again when connected.");
      return;
    }
    setIsStartingJob(true);
    try {
      resetJobStore();

      const tempJobId = `temp-${Date.now()}`;
      for (const uri of pendingPhotos) {
        await enqueueUpload(tempJobId, uri, "image/jpeg");
      }
      if (pendingRecording) {
        await enqueueUpload(tempJobId, pendingRecording, "audio/m4a");
      }

      const job = await createJob({
        customer_id: selectedCustomer.id,
        description: description || "On-site job",
      });
      setJobId(job.id);
      setActiveJob(job.id);

      await updateQueueJobId(tempJobId, job.id);

      await uploadMediaForJob(job.id);
      Alert.alert(
        "Job Created",
        `Job started for ${selectedCustomer.name}.${pendingPhotos.length + (pendingRecording ? 1 : 0) > 0 ? ` ${pendingPhotos.length + (pendingRecording ? 1 : 0)} media file(s) uploaded.` : " Take photos and record notes."}`
      );
    } catch (err) {
      console.error("Failed to create job:", err);
      Alert.alert("Error", "Failed to create job. Check your connection.");
    } finally {
      setIsStartingJob(false);
    }
  }, [isStartingJob, selectedCustomer, pendingPhotos, pendingRecording, description, resetJobStore, setActiveJob, uploadMediaForJob]);

  const handleCapturePhoto = useCallback(async () => {
    if (!cameraPermission?.granted) {
      const result = await requestPermission();
      if (!result.granted) return;
    }
    setShowCamera(true);
  }, [cameraPermission, requestPermission]);

  const handleTakePhoto = async (photo: { uri: string }) => {
    setCapturedPhotos((prev) => [...prev, photo.uri]);
    setShowCamera(false);

    if (jobId) {
      if (!checkIsOnline()) {
        await enqueueUpload(jobId, photo.uri, "image/jpeg");
      } else {
        try {
          const info = await FileSystem.getInfoAsync(photo.uri);
          const fileSize = info.exists ? info.size : 0;
          const upload = await getUploadUrl({
            job_id: jobId,
            file_name: `photo-${Date.now()}.jpg`,
            content_type: "image/jpeg",
            file_size: fileSize,
          });
          await FileSystem.uploadAsync(upload.upload_url, photo.uri, {
            fieldName: "file",
            httpMethod: "PUT",
            uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
          });
          await confirmUpload(upload.media_id);
          addMedia(upload.media_id);
        } catch (err) {
          console.error("Photo upload failed, enqueueing:", err);
          await enqueueUpload(jobId, photo.uri, "image/jpeg");
        }
      }
    } else {
      setPendingPhotos((prev) => [...prev, photo.uri]);
    }
  };

  const handleCaptureButtonPress = async () => {
    if (camera) {
      try {
        const photo = await camera.takePictureAsync();
        if (photo) handleTakePhoto(photo);
      } catch (e) {
        console.error("Failed to take photo:", e);
        Alert.alert("Error", "Failed to take photo");
      }
    }
  };

  const handleRecordVoice = useCallback(async () => {
    if (isRecording) {
      if (recordingRef.current) {
        try {
          await recordingRef.current.stopAndUnloadAsync();
          const uri = recordingRef.current.getURI();
          recordingRef.current = null;
          if (uri) {
            setRecordingUri(uri);
            setIsRecording(false);

            if (jobId) {
              if (!checkIsOnline()) {
                await enqueueUpload(jobId, uri, "audio/m4a");
              } else {
                try {
                  const info = await FileSystem.getInfoAsync(uri);
                  const fileSize = info.exists ? info.size : 0;
                  const upload = await getUploadUrl({
                    job_id: jobId,
                    file_name: `voice-${Date.now()}.m4a`,
                    content_type: "audio/m4a",
                    file_size: fileSize,
                  });
                  await FileSystem.uploadAsync(upload.upload_url, uri, {
                    fieldName: "file",
                    httpMethod: "PUT",
                    uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
                  });
                  await confirmUpload(upload.media_id);
                  addMedia(upload.media_id);
                } catch (err) {
                  console.error("Voice upload failed, enqueueing:", err);
                  await enqueueUpload(jobId, uri, "audio/m4a");
                }
              }
            } else {
              setPendingRecording(uri);
            }
          }
        } catch (err) {
          console.error("Failed to stop recording:", err);
          setIsRecording(false);
        }
      }
      return;
    }
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) return;

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await recording.startAsync();
      recordingRef.current = recording;
      setIsRecording(true);
    } catch (err) {
      console.error("Failed to record audio:", err);
      Alert.alert("Error", "Failed to record audio");
    }
  }, [isRecording, addMedia, jobId]);

  const playAudio = async () => {
    if (!recordingUri) return;
    if (sound) {
      await sound.stopAsync();
      await sound.unloadAsync();
      setSound(null);
      setIsPlaying(false);
      return;
    }
    try {
      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: recordingUri },
        { shouldPlay: true }
      );
      setSound(newSound);
      setIsPlaying(true);
      newSound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && !status.isPlaying) {
          setIsPlaying(false);
        }
      });
    } catch (err) {
      console.error("Failed to play audio:", err);
    }
  };

  useEffect(() => {
    return () => {
      if (sound) sound.unloadAsync();
    };
  }, [sound]);

  const handleFinishJob = () => {
    if (!jobId) return;
    router.push(`/job/${jobId}`);
  };

  if (showCamera) {
    return (
      <View className="flex-1">
        <CameraView
          className="flex-1"
          facing="back"
          ref={setCamera}
        >
          <View className="flex-1 justify-between pb-10">
            <TouchableOpacity
              className="self-start m-4 bg-white px-6 py-2 rounded-full"
              accessibilityLabel="Cancel camera"
              accessibilityRole="button"
              onPress={() => setShowCamera(false)}
            >
              <Text className="font-semibold">Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              className="self-center bg-white w-20 h-20 rounded-full border-4 border-gray-300 items-center justify-center"
              accessibilityLabel="Take photo"
              accessibilityRole="button"
              onPress={handleCaptureButtonPress}
            >
              <View className="w-16 h-16 rounded-full bg-gray-100" />
            </TouchableOpacity>
          </View>
        </CameraView>
      </View>
    );
  }

  return (
    <ScrollView className="flex-1 bg-gray-50 p-4">
      {!isOnline && (
        <View className="bg-red-100 border border-red-300 rounded-xl p-3 mb-4" accessibilityRole="alert">
          <Text className="text-red-700 text-sm font-medium text-center">
            You are offline — changes will sync when connected
          </Text>
        </View>
      )}
      <Text className="text-xl font-bold mb-6">Start Job</Text>

      {!jobId ? (
        <>
          <View className="bg-white p-4 rounded-xl mb-4">
            <View className="flex-row justify-between items-center mb-2">
              <Text className="font-semibold mb-2">Customer</Text>
              {isLoadingCustomers && <ActivityIndicator size="small" />}
            </View>
            {selectedCustomer ? (
              <TouchableOpacity
                className="bg-blue-50 p-3 rounded-lg"
                accessibilityLabel={`Selected customer: ${selectedCustomer.name}`}
                accessibilityRole="button"
                onPress={() => setShowCustomerPicker(true)}
              >
                <Text className="text-blue-800 font-medium">{selectedCustomer.name}</Text>
                {selectedCustomer.phone && (
                  <Text className="text-blue-600 text-sm">{selectedCustomer.phone}</Text>
                )}
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                className="bg-gray-100 p-3 rounded-lg"
                accessibilityLabel="Select a customer"
                accessibilityRole="button"
                onPress={() => setShowCustomerPicker(true)}
              >
                <Text className="text-gray-500">Select a customer...</Text>
              </TouchableOpacity>
            )}
          </View>

          <View className="bg-white p-4 rounded-xl mb-4">
            <Text className="font-semibold mb-2">Description</Text>
            <TextInput
              className="bg-gray-50 p-3 rounded-lg text-base"
              accessibilityLabel="Job description"
              placeholder="Job description (optional)"
              value={description}
              onChangeText={setDescription}
              multiline
            />
          </View>

          {(pendingPhotos.length > 0 || pendingRecording) && (
            <View className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 mb-4" accessibilityRole="alert">
              <Text className="text-yellow-700 text-sm font-medium">
                {pendingPhotos.length} photo(s)
                {pendingRecording ? ", 1 voice note" : ""} captured — will upload when job is created
              </Text>
            </View>
          )}

          <TouchableOpacity
            className={`p-6 rounded-xl items-center mb-4 ${isStartingJob ? "bg-blue-400" : "bg-blue-600"}`}
            accessibilityLabel={isStartingJob ? "Starting job" : "Begin job"}
            accessibilityRole="button"
            onPress={handleStartJob}
            disabled={isStartingJob}
          >
            <Text className="text-white text-lg font-bold">{isStartingJob ? "Starting..." : "Begin Job"}</Text>
            <Text className="text-blue-200 mt-1">Tap to create a new job record</Text>
          </TouchableOpacity>
        </>
      ) : (
        <>
          <View className="bg-white p-4 rounded-xl mb-4">
            <Text className="text-green-600 font-semibold mb-2">Job Active</Text>
            <Text className="text-gray-600">ID: {jobId.slice(0, 8)}...</Text>
            {selectedCustomer && (
              <Text className="text-gray-600">Customer: {selectedCustomer.name}</Text>
            )}
          </View>

          <TouchableOpacity
            className="bg-white p-4 rounded-xl mb-3 flex-row items-center"
            accessibilityLabel={`Take photos, ${capturedPhotos.length} taken`}
            accessibilityRole="button"
            onPress={handleCapturePhoto}
          >
            <View className="w-10 h-10 bg-blue-100 rounded-full items-center justify-center">
              <Text className="text-blue-600 text-lg font-bold">P</Text>
            </View>
            <Text className="ml-3 font-medium">Take Photos</Text>
            <Text className="ml-auto text-gray-400">{capturedPhotos.length} taken</Text>
          </TouchableOpacity>

          {capturedPhotos.length > 0 && (
            <ScrollView horizontal className="mb-3 -mx-4 px-4">
              {capturedPhotos.map((uri, i) => (
                <Image key={i} source={{ uri }} className="w-16 h-16 rounded-lg mr-2 bg-gray-200" />
              ))}
            </ScrollView>
          )}

          <TouchableOpacity
            className={`p-4 rounded-xl mb-3 flex-row items-center ${isRecording ? "bg-red-50" : "bg-white"}`}
            accessibilityLabel={isRecording ? "Stop recording" : recordingUri ? "Re-record voice note" : "Record voice note"}
            accessibilityRole="button"
            onPress={handleRecordVoice}
          >
            <View className={`w-10 h-10 rounded-full items-center justify-center ${isRecording ? "bg-red-100" : "bg-purple-100"}`}>
              <Text className={`text-lg font-bold ${isRecording ? "text-red-500" : "text-purple-600"}`}>
                {isRecording ? "R" : "M"}
              </Text>
            </View>
            <Text className="ml-3 font-medium">
              {isRecording ? "Stop Recording" : recordingUri ? "Re-record" : "Record Voice Note"}
            </Text>
          </TouchableOpacity>

          {recordingUri && !isRecording && (
            <TouchableOpacity
              className="bg-white p-3 rounded-xl mb-3 flex-row items-center border border-gray-200"
              accessibilityLabel={isPlaying ? "Stop playback" : "Play recording"}
              accessibilityRole="button"
              onPress={playAudio}
            >
              <View className="w-10 h-10 bg-green-100 rounded-full items-center justify-center">
                <Text className={`text-lg font-bold text-green-600`}>
                  {isPlaying ? "S" : "P"}
                </Text>
              </View>
              <Text className="ml-3 font-medium">{isPlaying ? "Stop" : "Play Recording"}</Text>
            </TouchableOpacity>
          )}

          <TouchableOpacity
            className="bg-green-600 p-4 rounded-xl mt-4 items-center"
            accessibilityLabel="Finish and view job"
            accessibilityRole="button"
            onPress={handleFinishJob}
          >
            <Text className="text-white font-bold text-lg">Finish & View Job</Text>
            <Text className="text-green-200 mt-1">Photos and voice notes are saved to this job</Text>
          </TouchableOpacity>
        </>
      )}

      <Modal visible={showCustomerPicker} animationType="slide" transparent>
        <View className="flex-1 bg-black/50 justify-end">
          <View className="bg-white rounded-t-2xl max-h-[70%]">
            <View className="p-4 border-b border-gray-200 flex-row justify-between items-center">
              <Text className="text-lg font-bold">Select Customer</Text>
              <TouchableOpacity
                accessibilityLabel="Close customer picker"
                accessibilityRole="button"
                onPress={() => setShowCustomerPicker(false)}
              >
                <Text className="text-blue-600 font-medium">Close</Text>
              </TouchableOpacity>
            </View>
            <FlatList
              data={customers}
              keyExtractor={(item) => item.id}
              className="p-4"
              renderItem={({ item }) => (
                <TouchableOpacity
                  className={`p-4 rounded-xl mb-2 ${
                    selectedCustomer?.id === item.id ? "bg-blue-100" : "bg-gray-50"
                  }`}
                  accessibilityLabel={`Customer: ${item.name}`}
                  accessibilityRole="button"
                  onPress={() => {
                    setSelectedCustomer(item);
                    setShowCustomerPicker(false);
                  }}
                >
                  <Text className="font-medium">{item.name}</Text>
                  {item.phone && <Text className="text-gray-500 text-sm">{item.phone}</Text>}
                  {item.email && <Text className="text-gray-400 text-sm">{item.email}</Text>}
                </TouchableOpacity>
              )}
              ListEmptyComponent={
                <Text className="text-center text-gray-400 py-8">No customers yet</Text>
              }
            />
            <TouchableOpacity
              className="bg-blue-600 mx-4 mb-6 p-4 rounded-xl items-center"
              accessibilityLabel="Create new customer"
              accessibilityRole="button"
              onPress={() => {
                setShowCustomerPicker(false);
                setShowCreateCustomer(true);
              }}
            >
              <Text className="text-white font-bold">+ Create New Customer</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <Modal visible={showCreateCustomer} animationType="slide" transparent>
        <View className="flex-1 bg-black/50 justify-end">
          <View className="bg-white rounded-t-2xl">
            <View className="p-4 border-b border-gray-200">
              <Text className="text-lg font-bold">Create Customer</Text>
            </View>
            <View className="p-4 space-y-3">
              <TextInput
                className="bg-gray-50 p-3 rounded-lg text-base"
                accessibilityLabel="Customer name, required"
                placeholder="Name *"
                value={newCustomerName}
                onChangeText={setNewCustomerName}
              />
              <TextInput
                className="bg-gray-50 p-3 rounded-lg text-base"
                accessibilityLabel="Customer email"
                placeholder="Email"
                value={newCustomerEmail}
                onChangeText={setNewCustomerEmail}
                keyboardType="email-address"
              />
              <TextInput
                className="bg-gray-50 p-3 rounded-lg text-base"
                accessibilityLabel="Customer phone"
                placeholder="Phone"
                value={newCustomerPhone}
                onChangeText={setNewCustomerPhone}
                keyboardType="phone-pad"
              />
              <TextInput
                className="bg-gray-50 p-3 rounded-lg text-base"
                accessibilityLabel="Customer address"
                placeholder="Address"
                value={newCustomerAddress}
                onChangeText={setNewCustomerAddress}
              />
              <View className="flex-row gap-3 mt-2">
                <TouchableOpacity
                  className="flex-1 bg-gray-200 p-4 rounded-xl items-center"
                  accessibilityLabel="Cancel create customer"
                  accessibilityRole="button"
                  onPress={() => setShowCreateCustomer(false)}
                >
                  <Text className="font-medium">Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  className={`flex-1 p-4 rounded-xl items-center ${isCreatingCustomer ? "bg-blue-400" : "bg-blue-600"}`}
                  accessibilityLabel={isCreatingCustomer ? "Creating customer" : "Create customer"}
                  accessibilityRole="button"
                  onPress={handleCreateCustomer}
                  disabled={isCreatingCustomer}
                >
                  <Text className="text-white font-bold">{isCreatingCustomer ? "Creating..." : "Create"}</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}
