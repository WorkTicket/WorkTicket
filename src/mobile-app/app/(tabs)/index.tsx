import { View, Text, FlatList, TouchableOpacity, ActivityIndicator } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { fetchJobs } from "@/api/client";

export default function JobListScreen() {
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["jobs"],
    queryFn: fetchJobs,
  });

  if (isLoading) {
    return (
      <View className="flex-1 justify-center items-center">
        <ActivityIndicator size="large" accessibilityLabel="Loading jobs" />
      </View>
    );
  }

  if (isError) {
    return (
      <View className="flex-1 justify-center items-center p-4">
        <Text className="text-red-500 text-center mb-4">Failed to load jobs</Text>
        <TouchableOpacity
          className="bg-blue-600 px-6 py-3 rounded-lg"
          accessibilityLabel="Retry loading jobs"
          accessibilityRole="button"
          onPress={() => refetch()}
        >
          <Text className="text-white font-semibold">Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View className="flex-1 bg-gray-50">
      <FlatList
        data={data?.jobs || []}
        keyExtractor={(item) => item.id}
        contentContainerClassName="p-4"
        renderItem={({ item }) => (
          <TouchableOpacity
            className="bg-white p-4 mb-3 rounded-xl shadow-sm"
            accessibilityLabel={`Job: ${item.description || "No description"}, ${item.address || ""}, Status: ${item.status}`}
            accessibilityRole="button"
            onPress={() => router.push(`/job/${item.id}`)}
          >
            <Text className="text-lg font-semibold">{item.description || "No description"}</Text>
            <Text className="text-gray-500 mt-1">{item.address}</Text>
            <Text className="text-sm mt-2">
              Status: <Text className="font-medium capitalize">{item.status}</Text>
            </Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text className="text-center text-gray-400 mt-20">No jobs scheduled today</Text>
        }
      />
      <TouchableOpacity
        className="bg-blue-600 mx-4 mb-6 p-4 rounded-xl"
        accessibilityLabel="Start new job"
        accessibilityRole="button"
        onPress={() => router.push("/(tabs)/start-job")}
      >
        <Text className="text-white text-center font-bold text-lg">Start New Job</Text>
      </TouchableOpacity>
    </View>
  );
}
