import { useCallback, useState } from "react";
import { View, Text, TouchableOpacity, ActivityIndicator, ScrollView, Alert } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJob, updateJob } from "@/api/client";
import { FUTURE_FEATURE_LABEL, FUTURE_FEATURE_NOTE } from "@/constants/product-rules";

const COMPLETABLE_STATUSES = new Set(["pending", "in_progress"]);

export default function JobDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [completing, setCompleting] = useState(false);

  const { data: job, isLoading } = useQuery({
    queryKey: ["job", id],
    queryFn: () => fetchJob(id!),
    enabled: !!id,
  });

  const handleMarkComplete = useCallback(async () => {
    if (!id || completing || !job || !COMPLETABLE_STATUSES.has(job.status)) return;
    setCompleting(true);
    try {
      await updateJob(id, { status: "completed" });
      await queryClient.invalidateQueries({ queryKey: ["job", id] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      Alert.alert("Job completed", "This job has been marked as complete.");
    } catch {
      Alert.alert("Error", "Failed to mark job as complete. Please try again.");
    } finally {
      setCompleting(false);
    }
  }, [id, completing, job, queryClient]);

  if (isLoading) {
    return (
      <View className="flex-1 justify-center items-center">
        <ActivityIndicator size="large" accessibilityLabel="Loading job details" />
        <Text className="text-gray-400 mt-2">Loading job...</Text>
      </View>
    );
  }

  const canComplete = job && COMPLETABLE_STATUSES.has(job.status);

  return (
    <ScrollView className="flex-1 bg-gray-50 p-4">
      <Text className="text-2xl font-bold mb-4">Job Details</Text>

      <View className="bg-white p-4 rounded-xl mb-4">
        <Text className="text-gray-500">Status</Text>
        <Text className="text-lg font-semibold capitalize">{job?.status}</Text>
        <Text className="text-gray-500 mt-2">Description</Text>
        <Text className="text-base">{job?.description || "Not specified"}</Text>
        <Text className="text-gray-500 mt-2">Address</Text>
        <Text className="text-base">{job?.address || "Not specified"}</Text>
      </View>

      {canComplete && (
        <TouchableOpacity
          className="bg-green-600 p-4 rounded-xl items-center mb-4"
          onPress={handleMarkComplete}
          disabled={completing}
          accessibilityLabel="Mark job complete"
          accessibilityRole="button"
        >
          {completing ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text className="text-white font-bold text-lg">Mark Complete</Text>
          )}
        </TouchableOpacity>
      )}

      {job?.status === "completed" && (
        <View className="bg-green-50 border border-green-200 p-4 rounded-xl mb-4">
          <Text className="text-green-800 font-medium text-center">Job completed</Text>
        </View>
      )}

      <View className="bg-white p-4 rounded-xl mb-4 border border-dashed border-gray-200">
        <View className="flex-row items-center justify-between mb-2">
          <Text className="text-base font-semibold">Voice Transcript</Text>
          <Text className="text-xs font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
            {FUTURE_FEATURE_LABEL}
          </Text>
        </View>
        <Text className="text-sm text-gray-500">{FUTURE_FEATURE_NOTE}</Text>
      </View>

      <TouchableOpacity
        className="bg-gray-200 p-4 rounded-xl items-center mb-8"
        accessibilityLabel="Back to jobs"
        accessibilityRole="button"
        onPress={() => router.back()}
      >
        <Text className="text-gray-700 font-medium">Back to Jobs</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
