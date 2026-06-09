import { View, Text, TouchableOpacity, ActivityIndicator } from "react-native";
import { useAuth, useUser } from "@clerk/clerk-expo";
import { useRouter } from "expo-router";

export default function ProfileScreen() {
  const { signOut, isLoaded: isAuthLoaded } = useAuth();
  const { user, isLoaded: isUserLoaded } = useUser();
  const router = useRouter();
  const userRole = (user?.publicMetadata?.role as string) || "";

  if (!isAuthLoaded || !isUserLoaded) {
    return (
      <View className="flex-1 bg-gray-50 justify-center items-center">
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <View className="flex-1 bg-gray-50 p-4">
      <View className="bg-white p-4 rounded-xl mb-4">
        <Text className="text-lg font-bold mb-2">{user?.fullName || "User"}</Text>
        <Text className="text-gray-500">{user?.primaryEmailAddress?.emailAddress || ""}</Text>
        {userRole ? (
          <Text className="text-gray-400 text-sm mt-1 capitalize">
            Role: {userRole}
          </Text>
        ) : null}
      </View>

      <TouchableOpacity
        className="bg-red-500 p-4 rounded-xl items-center mt-auto mb-8"
        accessibilityLabel="Sign out"
        accessibilityRole="button"
        onPress={() => {
          signOut();
          router.replace("/login");
        }}
      >
        <Text className="text-white font-bold">Sign Out</Text>
      </TouchableOpacity>
    </View>
  );
}
